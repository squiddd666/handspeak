"""Extract browser-compatible features from downloaded WLASL training clips."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

import run_dynamic_pose_training as extraction
from motion_window import align_window

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/opt/handspeak-training/wlasl-priority-six")
BASE = Path("/opt/handspeak-training/vocabulary-expansion-windowed-ordinary-source/development-features.json")
OUTPUT = ROOT / "development-features.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import cv2
    import mediapipe as mp
    manifest = json.loads((ROOT / "manifest.json").read_text())
    protocol = {
        "source": str(ROOT / "manifest.json"), "sourceSha256": digest(ROOT / "manifest.json"),
        "implementationSha256": digest(extraction.__file__),
        "handModelSha256": digest(extraction.HAND_MODEL),
        "encoders": {name: digest(REPO / name) for name in ("gesture-model.js", "motion-model.js")},
        "mediapipe": mp.__version__, "opencv": cv2.__version__, "poseModels": {},
        "sampledFrames": 60, "maxImageSide": 640, "handDetection": .65,
        "handPresence": .65, "handTracking": .6, "poseDetection": .5,
        "poseTracking": .5, "bodyMode": "per-frame pose", "labels": sorted({r["label"] for r in manifest}),
        "independentTestOpened": False, "deployed": False,
    }
    (ROOT / "frames").mkdir(exist_ok=True)
    (ROOT / "extraction-protocol.json").write_text(json.dumps(protocol, separators=(",", ":")))
    key = extraction.protocol_digest(protocol)
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(extraction.extract, [(row, str(ROOT), key) for row in manifest]))
    base = json.loads(BASE.read_text())
    known = {r["sha256"] for r in base}
    added = []
    for path in paths:
        row = align_window(json.loads(Path(path).read_text()))
        if row["sha256"] not in known and row.get("sequence") is not None:
            known.add(row["sha256"]); added.append(row)
    OUTPUT.write_text(json.dumps(base + added, separators=(",", ":")))
    print(json.dumps({"downloaded": len(manifest), "usableAdded": len(added),
                      "perWord": {label: sum(r["label"] == label for r in added)
                                  for label in sorted({r["label"] for r in manifest})}}))


if __name__ == "__main__":
    main()
