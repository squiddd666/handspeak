"""Download direct WLASL training-split sources for the six priority words.

YouTube and legacy SWF entries are skipped. Videos stay outside the served site.
"""
import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

WORDS = {"hello", "drink", "book", "hungry", "home", "fish"}
META = Path("/opt/handspeak-training/vocabulary-source-audit/WLASL_v0.3.json")
ROOT = Path("/opt/handspeak-training/wlasl-priority-six")


def main():
    rows = []
    entries = json.loads(META.read_text())
    for entry in entries:
        word = entry["gloss"].lower()
        if word not in WORDS:
            continue
        seen = set()
        for item in entry["instances"]:
            url = item["url"]
            path = urllib.parse.urlparse(url).path.lower()
            if item["split"] != "train" or url in seen or not path.endswith((".mp4", ".mov")):
                continue
            seen.add(url)
            output = ROOT / word / f"{item['video_id']}.mp4"
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                if not output.exists():
                    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(request, timeout=45) as response:
                        data = response.read(40_000_000)
                    if len(data) < 10_000:
                        raise ValueError("response was not a video")
                    output.write_bytes(data)
                subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(output)],
                    check=True, capture_output=True, text=True, timeout=20,
                )
            except Exception as error:
                output.unlink(missing_ok=True)
                print(word, item["video_id"], "skipped", type(error).__name__, flush=True)
                continue
            rows.append({
                "label": word.upper(), "split": "train",
                "participant": f"wlasl-{item['signer_id']}", "file": str(output),
                "source": url, "videoId": item["video_id"],
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            })
            print(word, item["video_id"], "ready", flush=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "manifest.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({word.upper(): sum(r["label"] == word.upper() for r in rows) for word in sorted(WORDS)}))


if __name__ == "__main__":
    main()
