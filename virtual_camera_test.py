"""
Virtual camera test for HandSpeak words.
Plays local MP4 videos through a canvas-based virtual camera and records recognition results.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
MEDIA = REPO / "media" / "signs"
REPORT_DIR = REPO / "reports" / "virtual-camera-all-words"

# Word -> video file mapping (only words with local videos)
WORD_VIDEOS = {
    # Default 6-word model
    "HELLO": "hello.mp4",
    "THANK YOU": "thank-you.mp4",
    "PLEASE": "please.mp4",
    "YES": "yes.mp4",
    "NO": "no.mp4",
    "FINISH": "finish.mp4",
    # Expanded 7-word model
    "DRINK": "drink.mp4",
    "WATER": "water.mp4",
    "BOOK": "book.mp4",
    "FOOD": "food.mp4",
    "HUNGRY": "hungry.mp4",
    "LIKE": "like.mp4",
    "GO": "go.mp4",
    # Capstone core words (videos available)
    "BELT": "belt.mp4",
    "EAT": "eat.mp4",
    "EMPTY": "empty.mp4",
    "PEG": "peg.mp4",
    "SOCCER": "soccer.mp4",
    "SQUEEZE": "squeeze.mp4",
    "VLOG": "vlog.mp4",
    # Single-word temporal models (videos available)
    "FISH": "fish.mp4",
    "NIGHT": "night.mp4",
    "PAIN": "pain.mp4",
    "SEE": "see.mp4",
    "SICK": "sick.mp4",
    # Other words with videos
    "HAVE": "have.mp4",
    "HOME": "home.mp4",
}

# How each locally-testable word is recognized in the app:
#   default  -> asl-words.json (6 words)
#   expanded -> asl-extra-words.json (7 words, via #expandedWords toggle)
#   pack     -> pack-dtw.json (the 5-word DTW model: FISH/PAIN/SEE/SICK/NIGHT)
DEFAULT_WORDS = ["HELLO", "THANK YOU", "PLEASE", "YES", "NO", "FINISH"]
EXPANDED_WORDS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]
PACK_WORDS = ["FISH", "PAIN", "SEE", "SICK", "NIGHT"]
PACK_MODEL = {"id": "pack-dtw", "name": "Pack words (DTW)"}

def word_vocab(word):
    if word in DEFAULT_WORDS:
        return "default"
    if word in EXPANDED_WORDS:
        return "expanded"
    if word in PACK_WORDS:
        return "pack"
    return None  # needs the server backend (capstone_asl_v3); not testable locally

# Words shown in the accuracy grid that require the PyTorch server backend
# (server.py -> capstone_asl_v3). Not testable in a local static virtual-camera run.
SERVER_WORDS = ["NAME", "HOME", "HAVE", "WANT", "LOVE", "BABY", "BELT", "EAT",
                "EMPTY", "PEG", "SOCCER", "SQUEEZE", "VLOG", "LOCK", "DUCK",
                "BASEBALLCAP", "OTHER", "WHATFOR", "DRAG", "MICROSCOPE", "PARTY",
                "DEMAND", "EDIT", "MECHANIC", "DEAF"]

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def start_server(port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), lambda *args, **kwargs: QuietHandler(*args, directory=str(REPO), **kwargs))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

VIRTUAL_CAMERA_SCRIPT = """
window.testCamera = {
    canvas: null,
    ctx: null,
    video: null,
    stream: null,
    events: [],
    observer: null,
    init() {
        const canvas = document.createElement('canvas');
        canvas.width = 640;
        canvas.height = 480;
        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        const video = document.createElement('video');
        video.muted = true;
        video.playsInline = true;
        this.canvas = canvas;
        this.ctx = ctx;
        this.video = video;
        this.events = [];

        // Override getUserMedia
        const self = this;
        navigator.mediaDevices.getUserMedia = async (constraints) => {
            return canvas.captureStream(30);
        };

        // Draw loop
        let lastDraw = -Infinity;
        function draw(now) {
            if (now - lastDraw < 33) { requestAnimationFrame(draw); return; }
            lastDraw = now;
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, 640, 480);
            if (video.readyState >= 2 && !video.ended) {
                const vRatio = video.videoWidth / video.videoHeight;
                const cRatio = 640 / 480;
                let dw, dh, dx, dy;
                if (vRatio > cRatio) {
                    dw = 640; dh = 640 / vRatio; dx = 0; dy = (480 - dh) / 2;
                } else {
                    dw = 480 * vRatio; dh = 480; dx = (640 - dw) / 2; dy = 0;
                }
                ctx.drawImage(video, dx, dy, dw, dh);
            }
            requestAnimationFrame(draw);
        }
        requestAnimationFrame(draw);

        // Monitor recognition results
        const liveLetter = document.querySelector('#liveLetter');
        const motionStatus = document.querySelector('#motionCaptureStatus');
        const recognitionFeedback = document.querySelector('#recognitionFeedback');
        if (liveLetter) {
            self.observer = new MutationObserver(() => {
                const text = liveLetter.textContent?.trim();
                if (text && text !== '\u2014' && text !== 'No reliable match') {
                    self.events.push({type: 'liveLetter', text, time: performance.now()});
                }
            });
            self.observer.observe(liveLetter, {childList: true, subtree: true, characterData: true});
        }
        if (motionStatus) {
            self.statusObserver = new MutationObserver(() => {
                const text = motionStatus.textContent?.trim();
                if (text) {
                    self.events.push({type: 'motionStatus', text, time: performance.now()});
                }
            });
            self.statusObserver.observe(motionStatus, {childList: true, subtree: true, characterData: true});
        }
        if (recognitionFeedback) {
            self.feedbackObserver = new MutationObserver(() => {
                const text = recognitionFeedback.textContent?.trim();
                if (text) {
                    self.events.push({type: 'feedback', text, time: performance.now()});
                }
            });
            self.feedbackObserver.observe(recognitionFeedback, {childList: true, subtree: true, characterData: true});
        }

        return true;
    },
    async playVideo(src) {
        const video = this.video;
        video.src = src;
        const loadResult = await new Promise((resolve) => {
            video.onloadedmetadata = () => resolve({ok: true});
            video.onerror = (e) => resolve({ok: false, error: 'Video load failed: ' + (video.error?.message || String(e.type))});
        });
        if (!loadResult.ok) throw new Error(loadResult.error);
        this.events = [];
        const start = performance.now();
        await video.play();
        await new Promise(resolve => { video.onended = resolve; });
        const end = performance.now();
        await new Promise(r => setTimeout(r, 2000));
        return {
            duration: video.duration,
            playbackMs: end - start,
            events: this.events.map(e => ({...e, time: e.time - start}))
        };
    },
    reset() {
        if (this.video) { this.video.pause(); this.video.src = ''; }
        this.events = [];
    }
};
"""

def test_word(page, word, video_path, use_expanded=False, category_model=None):
    """Test a single word through the virtual camera."""
    # Reset state
    page.evaluate("window.testCamera.reset()")
    page.evaluate("document.querySelector('#automaticWords').checked = true")
    page.evaluate("document.querySelector('#automaticWords').dispatchEvent(new Event('change'))")
    page.evaluate("document.querySelector('#sentenceAutoAdd').checked = false")

    # Set recognition mode to words
    page.select_option("#recognitionMode", "words")

    # Handle expanded words
    expanded_el = page.locator("#expandedWords")
    if use_expanded:
        page.evaluate("document.querySelector('#expandedWords').checked = true")
        page.evaluate("document.querySelector('#expandedWords').dispatchEvent(new Event('change'))")
    else:
        page.evaluate("document.querySelector('#expandedWords').checked = false")
        page.evaluate("document.querySelector('#expandedWords').dispatchEvent(new Event('change'))")

    # Handle category model (pack-dtw for the 5 pack words)
    if category_model:
        # Navigate to learn section to select vocabulary
        page.locator('.site-header nav a[href="#learn"]').click()
        page.select_option('#cameraVocabulary', category_model['id'])
        # Wait for vocabulary to switch (pack-dtw shows a 5-word preview, not the single word)
        try:
            page.wait_for_function(
                "() => /Pack words/i.test((document.querySelector('#activeVocabulary')?.textContent||'') + ' ' + (document.querySelector('#vocabularyCameraStatus')?.textContent||''))",
                timeout=15000)
        except Exception:
            pass
    else:
        # Make sure we're on default vocabulary
        page.locator('.site-header nav a[href="#workspace"]').click()

    # Ensure camera is running
    camera_status = page.locator("#cameraStatus").text_content()
    if "Camera off" in camera_status or "Live" not in camera_status:
        if "Live" in camera_status:
            page.click("#cameraButton")
            page.wait_for_timeout(500)
        page.click("#cameraButton")
        page.wait_for_function("document.querySelector('#cameraStatus').textContent.includes('Live')", timeout=30000)
        # Wait for tracker to be ready
        page.wait_for_function("document.querySelector('#cameraDiagnostics').textContent.includes('processedFps')", timeout=30000)
        page.wait_for_timeout(1500)

    # Play the video
    video_src = f"/__test_video/{word}.mp4"
    result = page.evaluate("""async (src) => {
        return await window.testCamera.playVideo(src);
    }""", video_src)

    # Extract recognized words from events
    recognized = []
    for event in result.get("events", []):
        if event.get("type") == "liveLetter":
            text = event.get("text", "").strip()
            if text and text not in ["\u2014", "No reliable match"]:
                recognized.append(text)

    # Get final status
    final_status = page.locator("#motionCaptureStatus").text_content()
    final_feedback = page.locator("#recognitionFeedback").text_content()
    final_live = page.locator("#liveLetter").text_content()

    return {
        "word": word,
        "recognized_words": recognized,
        "unique_recognized": list(dict.fromkeys(recognized)),
        "correct": word in recognized,
        "final_live": final_live,
        "final_status": final_status,
        "final_feedback": final_feedback,
        "video_duration": result.get("duration"),
        "playback_ms": result.get("playbackMs"),
        "event_count": len(result.get("events", [])),
    }


def main():
    parser = argparse.ArgumentParser(description="Test HandSpeak words using virtual camera")
    parser.add_argument("--words", help="Comma-separated words to test (default: all with videos)")
    parser.add_argument("--output", type=Path, default=REPORT_DIR)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    words_to_test = {}
    if args.words:
        for w in args.words.split(","):
            w = w.strip().upper()
            if w in WORD_VIDEOS:
                words_to_test[w] = WORD_VIDEOS[w]
    else:
        # Default: only words with a LOCAL model + local video (no server backend needed).
        local = DEFAULT_WORDS + EXPANDED_WORDS + PACK_WORDS
        words_to_test = {w: WORD_VIDEOS[w] for w in local if w in WORD_VIDEOS}

    if not words_to_test:
        print("No valid words to test.")
        sys.exit(1)

    # Start local server
    server = start_server(args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Server running at {url}")

    # Prepare report dir
    args.output.mkdir(parents=True, exist_ok=True)

    errors = []
    results = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required",
                      "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
                headless=True
            )
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(120000)
            page.on("pageerror", lambda e: errors.append(str(e)))

            # Route test videos
            def route_video(route, request):
                url_path = request.url.split("?")[0]
                name = url_path.split("/")[-1].replace(".mp4", "")
                video_path = MEDIA / words_to_test.get(name, "")
                if video_path.exists() and video_path.is_file():
                    data = video_path.read_bytes()
                    header = request.headers.get("range")
                    if header:
                        start, end = header.removeprefix("bytes=").split("-")
                        start = int(start)
                        end = min(int(end) if end else len(data) - 1, len(data) - 1)
                        route.fulfill(
                            status=206,
                            content_type="video/mp4",
                            headers={"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{len(data)}"},
                            body=data[start:end+1]
                        )
                    else:
                        route.fulfill(status=200, content_type="video/mp4", body=data)
                else:
                    route.fulfill(status=404, body=b"Not found")

            page.route("**/__test_video/*.mp4", route_video)

            # Inject virtual camera before any page load
            context.add_init_script(VIRTUAL_CAMERA_SCRIPT)

            # Load the app
            print(f"Loading app from {url} ...")
            page.goto(url, wait_until="domcontentloaded")

            # Wait for motion model to load
            print("Waiting for motion model...")
            page.wait_for_function(
                "document.querySelector('#motionModelStatus').textContent.includes('pretrained')",
                timeout=60000
            )

            # Disable face tracking for speed (inside collapsed details, use JS)
            page.evaluate("document.querySelector('#faceTrackingToggle').checked = false")
            page.evaluate("document.querySelector('#faceTrackingToggle').dispatchEvent(new Event('change'))")

            # Initialize virtual camera
            page.evaluate("window.testCamera.init()")

            # Start camera once
            print("Starting camera...")
            page.click("#cameraButton")
            page.wait_for_function("document.querySelector('#cameraStatus').textContent.includes('Live')", timeout=30000)
            page.wait_for_function("document.querySelector('#cameraDiagnostics').textContent.includes('processedFps')", timeout=30000)
            page.wait_for_timeout(2000)

            # Test each word
            total = len(words_to_test)
            for i, (word, video_file) in enumerate(words_to_test.items(), 1):
                print(f"[{i}/{total}] Testing {word} ...")
                try:
                    use_expanded = word in EXPANDED_WORDS
                    category = PACK_MODEL if word in PACK_WORDS else None
                    result = test_word(page, word, MEDIA / video_file, use_expanded=use_expanded, category_model=category)
                    results.append(result)
                    status = "PASS" if result["correct"] else "FAIL"
                    recognized = ", ".join(result["unique_recognized"]) if result["unique_recognized"] else "none"
                    print(f"  -> Recognized: {recognized} | {status}")
                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    results.append({"word": word, "error": str(e)})

            # Stop camera
            page.click("#cameraButton")
            browser.close()

    finally:
        server.shutdown()
        server.server_close()

    # Save JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "Local MP4 playback through 640x480 canvas captureStream, browser camera processing, automatic segmentation, face tracking off.",
        "server_url": url,
        "words_tested": len([r for r in results if "error" not in r]),
        "words_with_errors": len([r for r in results if "error" in r]),
        "correct_count": len([r for r in results if r.get("correct")]),
        "results": results,
        "page_errors": errors,
        "server_words": SERVER_WORDS,
    }

    json_path = args.output / "virtual-camera-results.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"\nJSON report saved to: {json_path}")

    # Generate HTML report
    generate_html_report(report, args.output / "virtual-camera-results.html")
    print(f"HTML report saved to: {args.output / 'virtual-camera-results.html'}")


def generate_html_report(report, path):
    results = report["results"]

    # Categorize words
    categories = {
        "Default 6-word model (local)": DEFAULT_WORDS,
        "Expanded 7-word preview (local)": EXPANDED_WORDS,
        "Pack words - pack-dtw model (NEW)": PACK_WORDS,
    }

    # Build word cells
    word_cells = []
    for cat_name, cat_words in categories.items():
        cells = []
        for word in cat_words:
            res = next((r for r in results if r.get("word") == word), None)
            if res and "error" not in res:
                correct = res.get("correct", False)
                recognized = res.get("unique_recognized", [])
                status_class = "pass" if correct else "fail"
                recog_text = ", ".join(recognized) if recognized else "No match"
                cells.append(f"""
                <div class="word-card {status_class}">
                    <div class="word-name">{word}</div>
                    <div class="word-detail">Recognized: {recog_text}</div>
                    <div class="word-status">{'CORRECT' if correct else 'INCORRECT'}</div>
                </div>
                """)
            elif res and "error" in res:
                cells.append(f"""
                <div class="word-card error">
                    <div class="word-name">{word}</div>
                    <div class="word-detail">Error during test</div>
                    <div class="word-status">ERROR</div>
                </div>
                """)
            else:
                cells.append(f"""
                <div class="word-card skipped">
                    <div class="word-name">{word}</div>
                    <div class="word-detail">No test run</div>
                    <div class="word-status">SKIPPED</div>
                </div>
                """)
        if cells:
            word_cells.append(f"<h3>{cat_name}</h3><div class='word-grid'>{''.join(cells)}</div>")

    # Server-only words (require the PyTorch capstone backend; not run locally)
    server_cells = "".join(
        f"""<div class="word-card skipped"><div class="word-name">{w}</div>
        <div class="word-detail">Needs server backend (capstone_asl_v3)</div>
        <div class="word-status">NOT RUN</div></div>"""
        for w in report.get("server_words", []))
    if server_cells:
        word_cells.append(f"<h3>Requires server backend (not tested in this local run)</h3><div class='word-grid'>{server_cells}</div>")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HandSpeak Virtual Camera Test Results</title>
<style>
:root {{ color-scheme: dark; }}
body {{ font-family: 'DM Sans', 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 2rem; }}
h1 {{ color: #7ee787; font-weight: 700; margin-bottom: 0.5rem; }}
h2 {{ color: #79c0ff; font-weight: 600; margin-top: 2rem; margin-bottom: 1rem; }}
h3 {{ color: #d2a8ff; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.meta {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 2rem; }}
.word-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
.word-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 1rem; text-align: center; transition: border-color 0.2s; }}
.word-card:hover {{ border-color: #58a6ff; }}
.word-card.pass {{ border-left: 4px solid #7ee787; }}
.word-card.fail {{ border-left: 4px solid #f85149; }}
.word-card.error {{ border-left: 4px solid #ffa657; }}
.word-card.skipped {{ border-left: 4px solid #8b949e; opacity: 0.7; }}
.word-name {{ font-weight: 700; font-size: 1.1rem; color: #f0f6fc; margin-bottom: 0.5rem; }}
.word-detail {{ font-size: 0.8rem; color: #8b949e; margin-bottom: 0.5rem; word-break: break-word; }}
.word-status {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }}
.word-card.pass .word-status {{ color: #7ee787; }}
.word-card.fail .word-status {{ color: #f85149; }}
.word-card.error .word-status {{ color: #ffa657; }}
.word-card.skipped .word-status {{ color: #8b949e; }}
.summary {{ display: flex; gap: 2rem; margin: 1.5rem 0; flex-wrap: wrap; }}
.summary-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 1rem 1.5rem; min-width: 140px; }}
.summary-box b {{ display: block; font-size: 1.5rem; color: #7ee787; margin-bottom: 0.25rem; }}
.summary-box span {{ font-size: 0.85rem; color: #8b949e; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }}
th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #30363d; }}
th {{ color: #79c0ff; font-weight: 600; background: #161b22; }}
tr:hover td {{ background: #161b22; }}
pre {{ background: #161b22; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>HandSpeak Virtual Camera Test Results</h1>
<div class="meta">
    {report['timestamp']} &middot; {report['words_tested']} words tested &middot; Method: {report['method']}
</div>
<div class="summary">
    <div class="summary-box"><b>{report['correct_count']}</b><span>Correctly recognized</span></div>
    <div class="summary-box"><b>{report['words_tested'] - report['correct_count']}</b><span>Missed / wrong</span></div>
    <div class="summary-box"><b>{report['words_with_errors']}</b><span>Errors</span></div>
    <div class="summary-box"><b>{len([e for e in report['page_errors'] if e])}</b><span>Page errors</span></div>
</div>
{''.join(word_cells)}
<h2>Detailed Results</h2>
<table>
<tr><th>Word</th><th>Recognized</th><th>Correct?</th><th>Final Status</th></tr>
"""
    for r in results:
        word = r.get("word", "?")
        if "error" in r:
            html += f"<tr><td>{word}</td><td colspan=3 style='color:#ffa657'>Error: {r['error']}</td></tr>\n"
        else:
            recog = ", ".join(r.get("unique_recognized", [])) or "—"
            correct = "YES" if r.get("correct") else "NO"
            status = (r.get("final_status") or "")[:80]
            html += f"<tr><td>{word}</td><td>{recog}</td><td>{correct}</td><td>{status}</td></tr>\n"

    html += """</table>
<h2>Raw JSON</h2>
<pre>""" + json.dumps(report, indent=2).replace("<", "&lt;").replace(">", "&gt;") + """</pre>
</body></html>"""

    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
