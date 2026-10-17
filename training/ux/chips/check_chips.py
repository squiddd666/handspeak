"""Functional check of the sentence-chip controls.

Self-contained: copies the repository module into a stub harness, serves it on 127.0.0.1,
and exercises chip rendering, the remove control, keyboard operation, focus handling and
the empty state in headless Chromium. MediaPipe, camera and the API are not involved.

Run: /opt/handspeak-training/venv/bin/python training/ux/chips/check_chips.py
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/opt/handspeak/repository")
MODULE = REPO / "experience-ui.js"
PORT = 8099


def serve():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).read()
        return None
    except Exception:
        pass
    process = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                               cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).read()
            return process
        except Exception:
            time.sleep(.25)
    raise SystemExit("harness server did not start")


from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    shutil.copyfile(MODULE, HERE / "experience-ui.js")
    server = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            errors, ignored = [], 0
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("response", lambda r: ignored + 1 if r.status == 404 and "/models/" in r.url else None)
            page.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="load")
            page.wait_for_selector(".word-chip")

            labels = page.locator(".word-chip-label")
            removes = page.locator(".word-chip-remove")
            results = {
                "chips": labels.count(),
                "removeLabels": [removes.nth(i).get_attribute("aria-label") for i in range(removes.count())],
                "editLabels": [labels.nth(i).get_attribute("aria-label") for i in range(labels.count())],
                "emptyState": page.locator(".chips-empty").count(),
            }

            labels.first.focus()
            page.keyboard.press("ArrowRight")
            results["arrowFocus"] = page.evaluate("document.activeElement.textContent")
            page.keyboard.press("End")
            results["endFocus"] = page.evaluate("document.activeElement.textContent")
            page.keyboard.press("Home")

            page.keyboard.press("Delete")
            page.wait_for_timeout(120)
            results["afterDelete"] = [labels.nth(i).inner_text() for i in range(labels.count())]
            results["deleteToast"] = page.locator("#toast").text_content()
            results["focusAfterDelete"] = page.evaluate("document.activeElement.className")

            removes.first.click()
            page.wait_for_timeout(120)
            results["afterRemove"] = [labels.nth(i).inner_text() for i in range(labels.count())]
            results["removeToast"] = page.locator("#toast").text_content()

            while labels.count():
                removes.first.click()
                page.wait_for_timeout(60)
            results["emptyAfterClearing"] = page.locator(".chips-empty").count()
            results["progress"] = page.locator("#sentenceProgress").text_content()
            browser.close()
    finally:
        if server:
            server.terminate()

    for key, value in results.items():
        print(f"{key}: {value}")
    print("pageErrors:", errors)
    ok = (results["chips"] == 3 and results["emptyState"] == 0
          and results["afterDelete"] == ["THANK", "YOU"] and results["afterRemove"] == ["YOU"]
          and "Removed HELLO" in (results["deleteToast"] or "")
          and results["focusAfterDelete"] == "word-chip-label"
          and results["emptyAfterClearing"] == 1 and not errors)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
