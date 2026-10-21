"""Extract browser-compatible hand and upper-body landmarks for nine words."""
import concurrent.futures
import argparse
import hashlib
import json
from pathlib import Path

import run_dynamic_pose_training as extraction
from motion_window import align_window

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/opt/handspeak-training/citizen-capstone-nine")
BASE = Path("/opt/handspeak-training/vocabulary-expansion-dynamic-pose/development-features.json")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    root = Path("/opt/handspeak-training/citizen-capstone-nine-test") if args.test else ROOT
    import cv2
    import mediapipe as mp
    manifest = json.loads((root / "manifest.json").read_text())
    protocol = {
        "source": str(root / "manifest.json"),
        "sourceSha256": digest(root / "manifest.json"),
        "implementationSha256": digest(extraction.__file__),
        "handModelSha256": digest(extraction.HAND_MODEL),
        "encoders": {name: digest(REPO / name)
                     for name in ("gesture-model.js", "motion-model.js")},
        "mediapipe": mp.__version__, "opencv": cv2.__version__, "poseModels": {},
        "sampledFrames": 60, "maxImageSide": 640, "handDetection": .65,
        "handPresence": .65, "handTracking": .6, "poseDetection": .5,
        "poseTracking": .5, "bodyMode": "per-frame pose",
        "labels": sorted({row["label"] for row in manifest}),
        "partition": ("Official ASL Citizen test participants" if args.test else
                      "Official ASL Citizen train and validation participants only"),
        "independentTestOpened": args.test, "deployed": False,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "frames").mkdir(exist_ok=True)
    path = root / "extraction-protocol.json"
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError("Extraction protocol changed")
    path.write_text(json.dumps(protocol, separators=(",", ":")))
    key = extraction.protocol_digest(protocol)
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(extraction.extract,
                              ((row, str(root), key) for row in manifest)))
    added = [align_window(json.loads(Path(item).read_text())) for item in paths]
    added = [row for row in added if row.get("sequence") is not None]
    base = [] if args.test else json.loads(BASE.read_text())
    known = {row["sha256"] for row in base}
    combined = base + [row for row in added if row["sha256"] not in known]
    output = root / ("test-features.json" if args.test else "development-features.json")
    output.write_text(json.dumps(combined, separators=(",", ":")))
    print(json.dumps({"downloaded": len(manifest), "usable": len(added),
                      "perWord": {label: {split: sum(row["label"] == label and
                                                       row["split"] == split for row in added)
                                          for split in ("train", "val")}
                                  for label in protocol["labels"]},
                      "outputSha256": digest(output)}, indent=2))


if __name__ == "__main__":
    main()
