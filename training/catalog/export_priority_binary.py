"""Export a development- and regression-pass binary model for browser staging."""
import hashlib
import json
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/opt/handspeak-training/priority-binary-hello-popsign-v2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((ROOT / "validation.json").read_text())["selected"]
    regression = json.loads((REPO / "reports/priority-six-popsign-binary-regression.json").read_text())
    result = next(row for row in regression["results"] if row["word"] == "HELLO")
    checkpoint = ROOT / "binary-private.pt"
    if not selected["passesValidation"] or sha(checkpoint) != selected["sha256"]:
        raise ValueError("HELLO checkpoint is not frozen")
    if result["correct"] < result["supportedTotal"] * .5 or result["negativeFalseAccepts"]:
        raise ValueError("HELLO did not pass regression")
    state = torch.load(checkpoint, weights_only=True)["state"]
    model = {
        "version": 1, "word": "HELLO", "encoding": "temporal-binary-v1",
        "threshold": selected["threshold"], "checkpointSha256": selected["sha256"],
        "weights": {name: value.tolist() for name, value in state.items()},
        "evaluation": {"development": selected["validation"], "regression": result},
        "status": "experimental",
    }
    output = REPO / "models/hello-binary.json"
    output.write_text(json.dumps(model, separators=(",", ":")) + "\n")
    print(output, sha(output))


if __name__ == "__main__":
    main()
