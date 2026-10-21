import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


CLIPS = {
    "HELLO": "/opt/handspeak/repository/media/signs/hello.mp4",
    "THANK YOU": "/opt/handspeak/repository/media/signs/thank-you.mp4",
    "PLEASE": "/opt/handspeak/repository/media/signs/please.mp4",
    "YES": "/opt/handspeak/repository/media/signs/yes.mp4",
    "NO": "/opt/handspeak/repository/media/signs/no.mp4",
    "FINISH": "/opt/handspeak/repository/media/signs/finish.mp4",
    "DRINK": "/opt/handspeak/repository/media/signs/drink.mp4",
    "WATER": "/opt/handspeak/repository/media/signs/water.mp4",
    "BOOK": "/opt/handspeak/repository/media/signs/book.mp4",
    "FOOD": "/opt/handspeak/repository/media/signs/food.mp4",
    "HUNGRY": "/opt/handspeak/repository/media/signs/hungry.mp4",
    "LIKE": "/opt/handspeak/repository/media/signs/like.mp4",
    "GO": "/opt/handspeak/repository/media/signs/go.mp4",
    "NAME": "/opt/handspeak-training/research-only/asl-dataset/name-1.mp4",
    "HOME": "/opt/handspeak-training/vocabulary-v7/videos/train/home/4a.8902-home-2023_01_29_12_35_50.245-0.mp4",
    "HAVE": "/opt/handspeak-training/vocabulary-expansion-joint50-balanced/videos/HAVE/4a.7007-have-2023_01_05_10_43_18.920-0.mp4",
    "WANT": "/opt/handspeak-training/daily-words/citizen-research/videos/test/5935927846691731-WANT.mp4",
    "LOVE": "/opt/handspeak-training/research-only/asl-dataset/love-1.mp4",
    "FISH": "/opt/handspeak/repository/media/signs/fish.mp4",
    "SICK": "/opt/handspeak/repository/media/signs/sick.mp4",
    "PAIN": "/opt/handspeak/repository/media/signs/pain.mp4",
    "NIGHT": "/opt/handspeak/repository/media/signs/night.mp4",
    "SEE": "/opt/handspeak/repository/media/signs/see.mp4",
}


def change(page, selector, checked):
    page.evaluate(
        """([selector, checked]) => {
          const input = document.querySelector(selector);
          input.checked = checked;
          input.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        [selector, checked],
    )


def main():
    categories_only = "--categories-only" in sys.argv
    only_arg = next((value.split("=", 1)[1] for value in sys.argv if value.startswith("--only=")), "")
    repeat_arg = next((value.split("=", 1)[1] for value in sys.argv if value.startswith("--repeat=")), "1")
    repeat_count = max(1, min(10, int(repeat_arg)))
    only = {value.strip().upper() for value in only_arg.split(",") if value.strip()}
    selected = lambda label: not only or label in only
    report_path = Path("reports/all-live-motion-virtual.json")
    results = json.loads(report_path.read_text())["results"] if categories_only and report_path.exists() else []

    def save_results():
        Path("reports/all-live-motion-virtual.json").write_text(
            json.dumps({"site": "https://handspeak.cvsu.dev", "results": results}, indent=2) + "\n"
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        server_sequences = []
        def capture_server_sequence(request):
            if request.url.endswith("/api/research-words") and request.post_data:
                try:
                    server_sequences.append(json.loads(request.post_data)["sequence"])
                except (KeyError, TypeError, json.JSONDecodeError):
                    pass
        page.on("request", capture_server_sequence)
        page.set_default_timeout(90000)
        page.route("https://fonts.googleapis.com/**", lambda route: route.abort())

        def serve_clip(route):
            key = urlparse(route.request.url).path.rsplit("/", 1)[-1].split(".")[0]
            label = key.replace("_", " ").upper()
            route.fulfill(body=Path(CLIPS[label]).read_bytes(), content_type="video/mp4")

        page.route("**/__virtual__/*.mp4", serve_clip)
        page.add_init_script(
            """window.audit={events:[],frames:0,tracked:0};
            navigator.mediaDevices.getUserMedia=async()=>{
              const c=document.createElement('canvas');c.width=480;c.height=640;
              const x=c.getContext('2d');window.auditVideo=document.createElement('video');
              auditVideo.muted=true;auditVideo.playsInline=true;
              setInterval(()=>{x.fillStyle='black';x.fillRect(0,0,c.width,c.height);
                if(auditVideo.readyState>=2&&!auditVideo.ended){
                  const s=Math.min(c.width/auditVideo.videoWidth,c.height/auditVideo.videoHeight);
                  const w=auditVideo.videoWidth*s,h=auditVideo.videoHeight*s;
                  x.drawImage(auditVideo,(c.width-w)/2,(c.height-h)/2,w,h);
                }},33);
              return c.captureStream(30);
            };"""
        )
        page.goto("https://handspeak.cvsu.dev/?motionAudit=1#workspace", wait_until="domcontentloaded")
        page.wait_for_function(
            "document.querySelector('#motionModelStatus').textContent.includes('pretrained words')"
        )
        page.evaluate("document.querySelector('#tutorialSkip')?.click()")
        change(page, "#faceTrackingToggle", False)
        page.evaluate(
            """document.querySelector('#recognitionMode').value='words';
            document.querySelector('#recognitionMode').dispatchEvent(new Event('change',{bubbles:true}));"""
        )
        page.evaluate(
            """async()=>{const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
            const original=vision.HandLandmarker.createFromOptions.bind(vision.HandLandmarker);
            vision.HandLandmarker.createFromOptions=async(files,options)=>{options.baseOptions.delegate='CPU';
              const detector=await original(files,options),detect=detector.detectForVideo.bind(detector);
              detector.detectForVideo=(video,t)=>{const r=detect(video,t);audit.frames++;
                if(r.landmarks?.length)audit.tracked++;return r};return detector};
            new MutationObserver(()=>audit.events.push({at:performance.now(),
              text:document.querySelector('#liveLetter').textContent,
              detail:document.querySelector('#liveConfidence').textContent}))
              .observe(document.querySelector('#liveResult'),{childList:true,subtree:true,characterData:true,attributes:true});}"""
        )
        page.click("#cameraButton")
        page.wait_for_function("document.querySelector('#cameraStatus').textContent.includes('Live')")

        def test_word(label, group):
            server_start = len(server_sequences)
            change(page, "#automaticWords", False)
            page.wait_for_timeout(700)
            change(page, "#automaticWords", True)
            page.evaluate("audit.events=[];audit.frames=0;audit.tracked=0")
            slug = label.lower().replace(" ", "_")
            page.evaluate(
                """async url=>{auditVideo.src=url;
                await new Promise((ok,no)=>{auditVideo.onloadedmetadata=ok;auditVideo.onerror=no});
                await auditVideo.play();await new Promise(ok=>auditVideo.onended=ok)}""",
                f"/__virtual__/{slug}.mp4",
            )
            # Allow the 600 ms quiet boundary and the 4.5 s maximum capture
            # boundary to finish before judging a clip that ends mid-motion.
            page.wait_for_timeout(5000)
            data = page.evaluate(
                """()=>({shown:document.querySelector('#liveLetter').textContent,
                detail:document.querySelector('#liveConfidence').textContent,
                status:document.querySelector('#motionCaptureStatus').textContent,
                research:document.querySelector('#researchWordsStatus').textContent,
                events:audit.events,frames:audit.frames,tracked:audit.tracked,
                diag:JSON.parse(document.querySelector('#cameraDiagnostics').textContent)})"""
            )
            result = {
                "expected": label,
                "group": group,
                "shown": data["shown"],
                "detail": data["detail"],
                "status": data["status"],
                "research": data["research"],
                "detectorFrames": data["frames"],
                "trackedFrames": data["tracked"],
                "lastCapture": data["diag"].get("lastCapture"),
                "events": data["events"][-5:],
            }
            sequence = page.evaluate("globalThis.__lastMotionSequence||null")
            if sequence:
                result["compatibilitySequence"] = sequence
            if group == "daily-server" and len(server_sequences) > server_start:
                result["compatibilitySequence"] = server_sequences[-1]
            results.append(result)
            save_results()
            print(json.dumps(result), flush=True)

        if not categories_only:
            if page.is_checked("#expandedWords"):
                change(page, "#expandedWords", False)
            for label in filter(selected, ["HELLO", "THANK YOU", "PLEASE", "YES", "NO", "FINISH"]):
                for _ in range(repeat_count): test_word(label, "default")

            change(page, "#expandedWords", True)
            page.wait_for_timeout(500)
            for label in filter(selected, ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]):
                for _ in range(repeat_count): test_word(label, "extra")

            change(page, "#expandedWords", False)
            change(page, "#researchWordsToggle", True)
            page.wait_for_timeout(500)
            for label in filter(selected, ["NAME", "HOME", "HAVE", "WANT", "LOVE"]):
                for _ in range(repeat_count): test_word(label, "daily-server")
                change(page, "#researchWordsToggle", False)
                page.wait_for_timeout(300)
                change(page, "#researchWordsToggle", True)
                page.wait_for_timeout(300)

        page.click("#cameraButton")
        for label in filter(selected, ["FISH", "SICK", "PAIN", "NIGHT", "SEE"]):
            page.evaluate(
                """value=>{const select=document.querySelector('#cameraVocabulary');
                select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));}""",
                f"single-{label.lower()}",
            )
            page.wait_for_function(
                "label=>document.querySelector('#motionModelStatus').textContent.includes(label)",
                arg=label,
            )
            page.click("#cameraButton")
            page.wait_for_function("document.querySelector('#cameraStatus').textContent.includes('Live')")
            for _ in range(repeat_count): test_word(label, "category")
            page.click("#cameraButton")
            page.wait_for_timeout(400)

        save_results()
        browser.close()


if __name__ == "__main__":
    main()
