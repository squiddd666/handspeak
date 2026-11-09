"""Verify all 198 videos against the live localhost server and decode each file.

Smoke-test server inference using existing cached held-out landmarks, without
opening the camera, changing consent UI, or storing request coordinates.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg

from build_local_research_videos import DEFAULT, EXTRA, friendly

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
CACHE = ROOT.parent / "hs-eval"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def fetch(path, method="GET", headers=None, data=None):
    request = urllib.request.Request(BASE + path, method=method, headers=headers or {},
                                    data=json.dumps(data).encode() if data is not None else None)
    with OPENER.open(request, timeout=60) as response:
        return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()


def check_video(item):
    code, headers, raw = fetch("/" + item["video"], "HEAD")
    path = ROOT / item["video"]
    assert code == 200 and headers["content-type"] == "video/mp4", item["label"]
    assert int(headers["content-length"]) == path.stat().st_size, item["label"]
    if item["localResearchOnly"]:
        assert headers.get("x-local-research-only") == "true", item["label"]
        code, headers, raw = fetch("/" + item["video"], headers={"Range": "bytes=0-1023"})
        assert code == 206 and raw == path.read_bytes()[:1024], item["label"]
    decoded = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"], capture_output=True, check=False)
    assert decoded.returncode == 0, (item["label"], decoded.stderr.decode())
    return {"label": item["label"], "video": item["video"], "http": 200, "decoded": True}


def main():
    manifest = json.loads((ROOT / "models/recognition-videos.json").read_text(encoding="utf-8"))
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(check_video, manifest["items"]))
    print(f"Live HTTP and complete decode: {len(checks)}/198 in {time.monotonic()-start:.2f}s", flush=True)
    statuses = {}
    for name, path in [("full100", "/api/capstone-asl/status"), ("beginner79", "/api/beginner-asl/status"),
                       ("daily5", "/api/research-words/status")]:
        code, headers, raw = fetch(path)
        data = json.loads(raw)
        assert data["available"], name
        if name != "daily5":
            assert data["runtimeReady"], name
        statuses[name] = data
    counts = {name: len(data["labels"]) for name, data in statuses.items()}
    assert counts == {"full100": 100, "beginner79": 79, "daily5": 5}, counts
    print("Loaded model labels:", counts, flush=True)
    small = DEFAULT + EXTRA + statuses["daily5"]["labels"]
    packs = json.loads((ROOT / "models/motion-categories/index.json").read_text(encoding="utf-8"))
    small += [label for pack in packs["groups"] for label in pack["labels"]]
    union = set(map(friendly, statuses["full100"]["labels"])) | set(statuses["beginner79"]["labels"]) | set(small)
    assert union == {item["label"] for item in manifest["items"]}
    inference = []
    for name, source, labels, path in [
        ("full100", CACHE / "features-test-merged.jsonl", {"BELT1", "DEAF1", "DUCK2"}, "/api/capstone-asl"),
        ("beginner79", CACHE / "beginner-100/features-need79.jsonl", {"GOODBYE", "SORRY", "MOTHER"}, "/api/beginner-asl"),
    ]:
        seen = set()
        with source.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                label, frames = row.get("label") or row.get("gloss"), row.get("frames", [])
                if row.get("split") != "test" or label not in labels or label in seen or not 5 <= len(frames) <= 90:
                    continue
                seen.add(label)
                payload = {"consent": True, "frames": frames}
                if name == "full100":
                    payload["vocabulary"] = "full"
                tick = time.monotonic()
                code, headers, raw = fetch(path, "POST", {"Content-Type": "application/json", "Origin": BASE}, payload)
                result = json.loads(raw)
                assert code == 200 and result["vocabularySize"] == (100 if name == "full100" else 79), result
                prediction = (result.get("predictions") or [{}])[0].get("label")
                item = {"model": name, "expected": label, "prediction": prediction, "file": row["file"],
                        "split": "test", "seconds": round(time.monotonic()-tick, 3),
                        "lowConfidence": result.get("lowConfidence", False)}
                inference.append(item)
                print("Inference:", item, flush=True)
                if seen == labels:
                    break
        assert seen == labels, (name, seen)
    restrictions = []
    for headers in [{"Host": "public.example.com"}, {"Forwarded": "for=127.0.0.1"},
                    {"X-Forwarded-Host": "public.example.com"}, {"Origin": "https://public.example.com"}]:
        try:
            fetch("/media/research-signs/name.mp4", headers=headers)
        except urllib.error.HTTPError as error:
            assert error.code == 403
            restrictions.append({"headers": headers, "status": error.code})
        else:
            raise AssertionError("Restricted research video was exposed")
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "baseUrl": BASE,
              "counts": manifest["counts"], "catalogEntries": 347, "httpAndDecodePassed": len(checks),
              "loadedModelLabels": counts, "runtimeTorch": statuses["full100"]["torchVersion"],
              "beginnerCheckpoint": statuses["beginner79"]["checkpoint"], "separateModelLabelUnion": len(union),
              "simultaneousRecognition": False,
              "simultaneousReason": "Category/daily selection replaces the active recognizer; full and Beginner captures suppress other recognition. Scores and greeting/component aliases are not calibrated for a unified classifier.",
              "inferenceSmokeTests": inference,
              "inferenceScope": "A few cached held-out landmark clips validate live inference routes, not live-camera accuracy or all-label recognition accuracy. No camera was started.",
              "localOnlyHTTPChecks": restrictions, "videos": checks}
    output = ROOT / "reports/watch-learn-198-verification.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Saved:", output, flush=True)


if __name__ == "__main__":
    main()
