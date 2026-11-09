"""Make a disposable loopback-only copy of the current app for CUA-driven tests.

This generator has no browser automation. UI actions belong to cua_repl. The
embedded source cannot request a physical camera and does not retain landmarks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "training/ux/motion_virtual_source.js"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_fixture(name: str, runner: bool = False, port: int = 8000, restart_stream: bool = False, checkpoint: bool = False) -> dict:
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local test server port")
    target = ROOT / name
    if target.parent.resolve() != ROOT.resolve() or target.suffix != ".html":
        raise ValueError("Fixture must be a new root-level .html file")
    if target.exists():
        raise FileExistsError(target)
    index_bytes = (ROOT / "index.html").read_bytes()
    bootstrap_bytes = BOOTSTRAP.read_bytes()
    manifest = json.loads((ROOT / "models/recognition-videos.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "models/motion-vocabulary.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in catalog["items"]}
    items = []
    for reference in manifest["items"]:
        item = by_id[reference["id"]]
        if item["video"] != reference["video"]:
            raise ValueError("Primary Watch clip differs from manifest")
        path = ROOT / item["video"]
        digest = sha(path.read_bytes())
        if reference.get("videoSha256") and digest != reference["videoSha256"]:
            raise ValueError(f"Clip identity changed: {item['id']}")
        items.append({"id": item["id"], "label": item["label"], "video": item["video"],
                      "videoSha256": digest, "recognition": item["recognition"],
                      "recognitionModes": item.get("recognitionModes", []),
                      "cameraGroups": item.get("cameraGroups", [])})
    if len(items) != 198 or len({item["id"] for item in items}) != 198:
        raise ValueError("Expected all 198 distinct recognition references")
    config = {"width": 960, "height": 720, "items": items,
              "indexSha256": sha(index_bytes), "bootstrapSha256": sha(bootstrap_bytes)}
    runtime_files = ["app.js", "landmark-capture.js", "capstone-recognition.js", "beginner-recognition.js",
                     "motion-studio.js", "research-words.js", "vocabulary-library.js", "recognition-library.js",
                     "motion-model.js", "expanded-motion.js", "hello-binary.js", "capstone_asl_v3.py", "beginner_asl.py",
                     "sign_features.py", "motion_calibration.py", "motion-accuracy.js", "models/motion-word-accuracy.json"]
    runtime_files += [name for name in ("body-hand-recovery.js", "hand-recovery-worker.js") if (ROOT / name).exists()]
    runtime_files += [name for name in ("landmark-frame-geometry.js",) if (ROOT / name).exists()]
    runtime_files += [name for name in ("handshape_features.py", "handshape_model.py", "handshape_inference.py") if (ROOT / name).exists()]
    config["runtimeSha256"] = {name: sha((ROOT / name).read_bytes()) for name in runtime_files}
    config["manualModelSha256"] = {name: sha((ROOT / name).read_bytes()) for name in
        ["models/asl-words.json", "models/asl-extra-words.json", "models/research-words.json",
         "models/hello-binary.json", "models/baby-binary.json", "models/water-binary.json",
         "models/motion-categories/index.json", "models/motion-categories/pack-dtw.json"]}
    candidates = {"beginner": [ROOT / "models/beginner-repaired-v2.pt", ROOT / "models/beginner-repaired-v1.pt", ROOT.parent / "hs-eval/models/beginner-need79-v1.pt"],
                  "capstone": [ROOT / "third_party/microsoft_asl_citizen/capstone100-repaired-v1.pt",
                               ROOT / "third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt"]}
    config["activeModelSha256"] = {family: sha(next(path for path in paths if path.exists()).read_bytes())
                                   for family, paths in candidates.items()}
    if (ROOT / "models/motion-calibration.json").exists():
        config["calibrationSha256"] = sha((ROOT / "models/motion-calibration.json").read_bytes())
        release = json.loads((ROOT / "models/motion-calibration.json").read_text(encoding="utf-8"))
        config["activeAuxiliaryModelSha256"] = {
            family: sha((ROOT / profile["auxiliary"]["checkpoint"]).read_bytes())
            for family, profile in release["models"].items() if profile.get("auxiliary")}
    runner_bytes = (ROOT / "training/ux/motion_virtual_runner.js").read_bytes() if runner else b""
    if runner:
        config["runnerSha256"] = sha(runner_bytes)
        config["restartVirtualStreamEachReference"] = restart_stream
    if checkpoint:
        if not runner:
            raise ValueError('Checkpointing requires the explicit diagnostic runner')
        config['auditCheckpoint'] = {'endpoint': '/__motion_audit__/checkpoint', 'token': secrets.token_urlsafe(32)}
    # Classic bootstrap executes before ALL deferred production modules.
    code = "\n<script>\nwindow.HANDSPEAK_VIRTUAL_FIXTURE = " + json.dumps(config, ensure_ascii=True) + ";\n"
    code += bootstrap_bytes.decode("utf-8").replace("</script", "<\\/script")
    code += "\n" + runner_bytes.decode("utf-8").replace("</script", "<\\/script") + "\n</script>\n"
    page = index_bytes.replace(b"<head>", b"<head>" + code.encode("utf-8"), 1)
    if page == index_bytes:
        raise ValueError("Could not find the app head")
    target.write_bytes(page)
    return {"fixture": str(target), "url": f"http://127.0.0.1:{port}/{name}#learn",
            "labels": len(items), "indexSha256": config["indexSha256"],
            "bootstrapSha256": config["bootstrapSha256"], "fixtureSha256": sha(page)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="motion-virtual-camera-test-20261106.html")
    parser.add_argument("--runner", action="store_true", help="Add an explicit visible batch-run button to the disposable fixture")
    parser.add_argument("--port", type=int, default=8000, help="Port of the local test server; does not start a server")
    parser.add_argument("--restart-stream", action="store_true", help="Rebind only the virtual stream through public camera controls before each reference")
    parser.add_argument("--checkpoint", action="store_true", help="Save scalar outcomes to the separate loopback audit server after each attempt")
    args = parser.parse_args()
    print(json.dumps(make_fixture(args.name, args.runner, args.port, args.restart_stream, args.checkpoint), indent=2))
