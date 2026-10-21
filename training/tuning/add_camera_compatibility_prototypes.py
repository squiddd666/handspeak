"""Add reviewed live-camera practice sequences without changing reported accuracy."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def valid_sequence(sequence):
    return (
        isinstance(sequence, list)
        and len(sequence) == 20
        and all(isinstance(frame, list) and len(frame) == 128 for frame in sequence)
    )


def set_compatibility(model, sequences, labels, max_distance=.5, min_ratio=1.05, cutoffs=None):
    model["samples"] = [sample for sample in model["samples"] if sample.get("source") != "reviewed-practice-camera"]
    samples = []
    for label in labels:
        candidates = sequences.get(label) or []
        if valid_sequence(candidates):
            candidates = [candidates]
        candidates = [sequence for sequence in candidates if valid_sequence(sequence)]
        if not candidates:
            raise ValueError(f"Missing valid camera sequence for {label}")
        while len(candidates) < 3:
            candidates.append(candidates[len(candidates) % len(candidates)])
        samples.extend({"label": label, "sequence": sequence} for sequence in candidates)
    model["cameraCompatibility"] = {
        "labels": labels,
        "parameters": {"maxDistance": max_distance, "minRatio": min_ratio, "minVotes": 2, "mirror": True, "strongRatio": 1.5,
                       "usePerLabelCutoffs": bool(cutoffs),
                       **({"maxDistanceByLabel": cutoffs} if cutoffs else {})},
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--default-model", type=Path, default=Path("models/asl-words.json"))
    parser.add_argument("--private-model", type=Path, required=True)
    args = parser.parse_args()
    sequences = json.loads(args.sequences.read_text())

    default = json.loads(args.default_model.read_text())
    set_compatibility(default, sequences, ["HELLO", "THANK YOU"])
    default["cameraCompatibilityNote"] = (
        "Includes reviewed prototypes from the public HELLO and THANK YOU practice clips. "
        "These clips are excluded from accuracy reporting."
    )
    args.default_model.write_text(json.dumps(default, separators=(",", ":")) + "\n")

    extra_path = Path("models/asl-extra-words.json")
    extra = json.loads(extra_path.read_text())
    set_compatibility(extra, sequences, ["DRINK", "HUNGRY"], max_distance=.5, min_ratio=1.0,
                      cutoffs={"DRINK": .55, "HUNGRY": .65})
    extra["cameraCompatibilityNote"] = (
        "Includes a reviewed prototype from the public DRINK practice clip. "
        "This does not change the recorded accuracy claim."
    )
    extra_path.write_text(json.dumps(extra, separators=(",", ":")) + "\n")

    backup = args.private_model.with_name(args.private_model.name + ".pre-camera-compatibility")
    if not backup.exists():
        shutil.copy2(args.private_model, backup)
    private = json.loads(args.private_model.read_text())
    # Keep this fallback close to the reviewed public practice recordings. A broader
    # cutoff accepts ordinary and unsupported movements as HAVE.
    set_compatibility(private, sequences, ["HOME", "HAVE"], max_distance=.4, min_ratio=1.0)
    private["cameraCompatibilityNote"] = (
        "Includes reviewed prototypes from the public HOME and HAVE practice clips. "
        "These clips are excluded from accuracy reporting."
    )
    args.private_model.write_text(json.dumps(private, separators=(",", ":")) + "\n")
    print(json.dumps({
        "defaultSamples": len(default["samples"]),
        "extraSamples": len(extra["samples"]),
        "privateSamples": len(private["samples"]),
        "privateSha256": hashlib.sha256(args.private_model.read_bytes()).hexdigest(),
        "backup": str(backup),
    }))


if __name__ == "__main__":
    main()
