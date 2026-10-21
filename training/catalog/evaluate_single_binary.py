"""Evaluate one frozen hand-only binary candidate without threshold tuning."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

import train_expansion_batch as batch
from train_priority_binary import BinaryTemporal


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--word", required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", action="append", type=Path, required=True)
    args = parser.parse_args()
    word = args.word.upper()
    selected = json.loads((args.experiment / "validation.json").read_text())["selected"]
    checkpoint = args.experiment / "binary-private.pt"
    if not selected["passesValidation"] or sha(checkpoint) != selected["sha256"]:
        raise ValueError("Candidate is not a frozen development pass")
    rows, seen = [], set()
    for source in args.source:
        for row in json.loads(source.read_text()):
            if row.get("sequence") is None or row.get("sha256") in seen:
                continue
            seen.add(row["sha256"])
            item = dict(row); item["body"] = [None] * len(item["rawFrames"])
            rows.append(item)
    model = BinaryTemporal(32)
    model.load_state_dict(torch.load(checkpoint, weights_only=True)["state"])
    model.eval()
    inputs = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in rows]))
    with torch.no_grad():
        scores = model(inputs).sigmoid().numpy()
    accepted = scores >= selected["threshold"]
    positive = np.array([row["label"] == word for row in rows])
    result = {"word": word, "correct": int(np.sum(accepted & positive)),
              "total": int(np.sum(positive)),
              "negativeFalse": int(np.sum(accepted & ~positive)),
              "negativeTotal": int(np.sum(~positive)),
              "threshold": selected["threshold"],
              "checkpointSha256": selected["sha256"],
              "sourceSha256": {str(source): sha(source) for source in args.source},
              "passes": (int(np.sum(accepted & positive)) >= int(np.sum(positive)) * .5
                         and int(np.sum(accepted & ~positive)) == 0
                         and int(np.sum(positive)) > 0),
              "scope": "Frozen hand-only classifier and development threshold; no test tuning.",
              "deployed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
