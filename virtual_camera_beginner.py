"""Play each online Beginner Watch & Learn clip through a virtual camera on the live site."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
SITE = "https://handspeak.cvsu.dev"
OUT = REPO / "reports" / "virtual-camera-beginner-online"
CLOSED = {"SCHOOL", "SISTER", "WE"}

INIT = r"""
window.testCamera = {
  init() {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    document.body.appendChild(canvas);
    const ctx = canvas.getContext('2d', {willReadFrequently: true});
    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.loop = false;
    this.canvas = canvas;
    this.video = video;
    const stream = canvas.captureStream(0);
    const track = stream.getVideoTracks()[0];
    setInterval(() => track.requestFrame(), 33);
    navigator.mediaDevices.getUserMedia = async () => stream;
    const draw = () => {
      ctx.fillStyle = '#111';
      ctx.fillRect(0, 0, 640, 480);
      if (video.readyState >= 2) {
        const ratio = video.videoWidth / Math.max(1, video.videoHeight);
        const box = 640 / 480;
        let dw, dh, dx, dy;
        if (ratio > box) { dw = 640; dh = 640 / ratio; dx = 0; dy = (480 - dh) / 2; }
        else { dh = 480; dw = 480 * ratio; dy = 0; dx = (640 - dw) / 2; }
        ctx.drawImage(video, dx, dy, dw, dh);
      }
      requestAnimationFrame(draw);
    };
    requestAnimationFrame(draw);
  },
  async play(src) {
    const video = this.video;
    if (video.getAttribute('src') !== src) {
      video.src = src;
      await new Promise((resolve, reject) => {
        video.onloadeddata = () => resolve();
        video.onerror = () => reject(new Error('clip failed to load'));
      });
    }
    video.loop = false;
    video.playbackRate = 0.35;
    video.currentTime = 0;
    await video.play();
    return {width: video.videoWidth, height: video.videoHeight, duration: video.duration};
  }
};
"""


def words():
    ready = json.loads((REPO / "models" / "beginner-ready-labels.json").read_text(encoding="utf-8-sig"))
    extra = json.loads((REPO / "models" / "beginner-practice-extra.json").read_text(encoding="utf-8-sig"))
    ids = {**ready["ids"], **extra["ids"]}
    labels = list(ready["labels"]) + [name for name in extra["labels"] if name not in ready["labels"]]
    return [(name, ids[name]) for name in labels]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = words()
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        catalog = catalog[: int(sys.argv[1])]
    elif len(sys.argv) > 1:
        wanted = {name.strip().upper() for name in sys.argv[1].split(",")}
        catalog = [(name, clip_id) for name, clip_id in catalog if name in wanted]
    results = []
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required", "--use-gl=angle", "--use-angle=d3d11", "--enable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(90000)
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.add_init_script(INIT)
        print(f"Opening {SITE}")
        page.goto(SITE, wait_until="domcontentloaded")
        page.evaluate("window.testCamera.init()")
        page.evaluate("""() => {
          const original = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const url = String(args[0]?.url || args[0] || '');
            if (window.__testMinScore && url.includes('/api/beginner-asl') && !url.includes('status') && args[1] && args[1].body) {
              const payload = JSON.parse(args[1].body);
              payload.minScore = window.__testMinScore;
              args[1] = Object.assign({}, args[1], {body: JSON.stringify(payload)});
            }
            const response = await original(...args);
            if (url.includes('/api/beginner-asl') && !url.includes('status')) {
              window.__lastBeginner = await response.clone().json();
            }
            return response;
          };
        }""")
        page.wait_for_function(
            "() => (document.querySelector('#beginnerStatus')?.textContent || '').includes('ready Beginner words')",
            timeout=60000,
        )
        page.evaluate("""() => {
          const consent = document.querySelector('#beginnerConsent');
          consent.checked = true;
          consent.dispatchEvent(new Event('change'));
          const face = document.querySelector('#faceTrackingToggle');
          if (face && face.checked) { face.checked = false; face.dispatchEvent(new Event('change')); }
        }""")
        page.click("#cameraButton")
        page.wait_for_function("() => (document.querySelector('#cameraStatus')?.textContent || '').includes('Live')", timeout=90000)
        print("Camera live")
        page.evaluate("""async () => {
          await window.testCamera.play('https://handspeak.cvsu.dev/media/signs/angry.mp4');
          document.querySelector('#beginnerRecord')?.click();
        }""")
        page.wait_for_function(
            """() => /Possible match:|No confident|No prediction|Not enough|timed out|Could not|Tracking stopped/.test(document.querySelector('#beginnerStatus')?.textContent || '')""",
            timeout=60000,
        )
        print("Tracker warm-up:", page.locator("#beginnerStatus").inner_text(), flush=True)
        for index, (name, clip_id) in enumerate(catalog, 1):
            print(f"[{index}/{len(catalog)}] {name}", flush=True)
            try:
                page.evaluate(
                    """(name) => document.querySelector(`button[data-sign-label="${name}"]`)?.click()""",
                    name,
                )
                page.wait_for_function(
                    """(id) => (document.querySelector('#signExampleVideo')?.getAttribute('src') || '').includes(id + '.mp4')""",
                    arg=clip_id,
                    timeout=20000,
                )
                page.evaluate("() => document.querySelector('#signExamplePractice')?.click()")
                page.wait_for_timeout(300)
                info = page.evaluate(
                    """async () => {
                      const video = window.testCamera.video;
                      const src = new URL(document.querySelector('#signExampleVideo').src, location.href).href;
                      if (video.getAttribute('src') !== src) {
                        video.src = src;
                        await new Promise((resolve, reject) => {
                          video.onloadeddata = () => resolve();
                          video.onerror = () => reject(new Error('clip failed to load'));
                        });
                      }
                      video.loop = false;
                      video.playbackRate = 0.35;
                      video.pause();
                      video.currentTime = 0;
                      return {width: video.videoWidth, height: video.videoHeight, duration: video.duration};
                    }"""
                )
                page.evaluate("""() => { window.__lastBeginner = null; document.querySelector('#beginnerRecord')?.click(); }""")
                page.wait_for_function(
                    """() => /Recording for four seconds|Not enough|Could not|Enable landmark|Tracking stopped/.test(document.querySelector('#beginnerStatus')?.textContent || '')""",
                    timeout=20000,
                )
                page.evaluate("() => window.testCamera.video.play()")
                page.wait_for_function(
                    """() => {
                      const text = document.querySelector('#beginnerStatus')?.textContent || '';
                      return !text.includes('Recording for four seconds') && /Possible match:|No confident|No prediction|Not enough|timed out|Could not|Recognition failed|Tracking stopped|Enable landmark/.test(text);
                    }""",
                    timeout=45000,
                )
                status = page.locator("#beginnerStatus").inner_text()
                live = page.locator("#liveLetter").inner_text()
                closed = page.locator("#beginnerWords").get_attribute("data-closed-labels") or ""
                api = page.evaluate("() => window.__lastBeginner || null")
                predicted = ""
                if "Possible match:" in status:
                    predicted = status.split("Possible match:", 1)[1].split(".", 1)[0].strip()
                top = (api or {}).get("predictions") or []
                row = {
                    "word": name,
                    "clip": clip_id,
                    "predicted": predicted or (top[0]["label"] if top else ""),
                    "accepted": predicted == name,
                    "top1": top[0]["label"] if top else "",
                    "top1Score": top[0].get("score") if top else None,
                    "correct": bool(top) and top[0]["label"] == name,
                    "closed": closed,
                    "status": status,
                    "live": live,
                    "video": info,
                    "top5": [{"label": item.get("label"), "score": item.get("score")} for item in top[:5]],
                }
            except Exception as exc:
                row = {"word": name, "clip": clip_id, "error": str(exc)}
            results.append(row)
            mark = "PASS" if row.get("correct") else ("ERROR" if row.get("error") else "FAIL")
            print(
                f"  {mark} top1={row.get('top1') or '-'} score={row.get('top1Score')} shown={row.get('status') or row.get('error')}",
                flush=True,
            )
            report_name = "virtual-camera-beginner-slow.json" if len(sys.argv) > 1 else "virtual-camera-beginner-results.json"
            (OUT / report_name).write_text(
                json.dumps({"site": SITE, "results": results, "pageErrors": errors}, indent=2),
                encoding="utf-8",
            )
        browser.close()
    correct = sum(1 for row in results if row.get("correct"))
    accepted = sum(1 for row in results if row.get("accepted"))
    print(f"\n{correct}/{len(results)} top-1 matched the clip; {accepted}/{len(results)} passed the on-screen confidence check")
    print(OUT / ("virtual-camera-beginner-slow.json" if len(sys.argv) > 1 else "virtual-camera-beginner-results.json"))


if __name__ == "__main__":
    main()
