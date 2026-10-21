"""Export the frozen development- and test-pass BABY hand-only model."""
import hashlib
import json
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/opt/handspeak-training/priority-binary-baby-citizen-v1")
REPORT = REPO / "reports/capstone-nine-baby-hand-only.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((ROOT / "validation.json").read_text())["selected"]
    test = json.loads(REPORT.read_text())
    checkpoint = ROOT / "binary-private.pt"
    if not selected["passesValidation"] or sha(checkpoint) != selected["sha256"]:
        raise ValueError("BABY checkpoint is not frozen")
    if not test["passes"] or test["checkpointSha256"] != selected["sha256"]:
        raise ValueError("BABY did not pass its frozen test")
    state = torch.load(checkpoint, weights_only=True)["state"]
    model = {"version": 1, "word": "BABY", "encoding": "temporal-binary-v1",
             "threshold": selected["threshold"],
             "checkpointSha256": selected["sha256"],
             "weights": {name: value.tolist() for name, value in state.items()},
             "evaluation": {"development": selected["validation"], "test": test},
             "status": "experimental"}
    output = REPO / "models/baby-binary.json"
    output.write_text(json.dumps(model, separators=(",", ":")) + "\n")
    print(output, sha(output))


if __name__ == "__main__":
    main()
