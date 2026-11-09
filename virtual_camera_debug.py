"""See whether the virtual camera actually shows a Watch & Learn clip."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
OUT = REPO / "reports" / "virtual-camera-beginner-online"
INIT = (REPO / "virtual_camera_beginner.py").read_text(encoding="utf-8")
start = INIT.index('INIT = r"""') + len('INIT = r"""')
end = INIT.index('"""', start)
script = INIT[start:end]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required", "--use-gl=angle", "--use-angle=swiftshader"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.add_init_script(script)
    page.goto("https://handspeak.cvsu.dev", wait_until="domcontentloaded")
    page.evaluate("window.testCamera.init()")
    page.wait_for_function("() => (document.querySelector('#beginnerStatus')?.textContent || '').includes('ready Beginner words')")
    page.click("#cameraButton")
    page.wait_for_function("() => (document.querySelector('#cameraStatus')?.textContent || '').includes('Live')")
    info = page.evaluate("""async () => {
      const meta = await window.testCamera.play('https://handspeak.cvsu.dev/media/signs/angry.mp4');
      const video = document.querySelector('#webcam');
      const t0 = video.currentTime;
      await new Promise(r => setTimeout(r, 1000));
      return {meta, t0, t1: video.currentTime, w: video.videoWidth, h: video.videoHeight, ready: video.readyState, paused: video.paused};
    }""")
    page.locator("#webcam").screenshot(path=str(OUT / "webcam-angry.png"))
    print(json.dumps(info))
    browser.close()
