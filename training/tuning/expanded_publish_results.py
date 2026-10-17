"""Write the contiguous-basis recorded results for the seven expanded words.

Same model, same prototypes, same parameters: only the measurement basis changes (frames
sampled contiguously over the signing window, as the live camera pipeline does, instead of
uniformly across the whole clip). The previous numbers are kept in protocolHistory.
"""
import json
from collections import Counter
from pathlib import Path

SITE = Path("/opt/handspeak/repository")
ACCURACY = SITE / "models/motion-word-accuracy.json"
EVAL = SITE / "models/asl-extra-words-evaluation.json"

RESULTS = {
    "DRINK": {"correct": 7, "total": 8},
    "WATER": {"correct": 5, "total": 8},
    "BOOK": {"correct": 5, "total": 8},
    "FOOD": {"correct": 5, "total": 5},
    "HUNGRY": {"correct": 4, "total": 5},
    "LIKE": {"correct": 3, "total": 6},
    "GO": {"correct": 1, "total": 6},
}
NEGATIVE = {"false": 11, "total": 16}
UNTACKED = 2

accuracy = json.loads(ACCURACY.read_text())
profile = accuracy["profiles"]["expanded"]
previous_words = dict(profile["words"])
profile["model"] = "Expanded preview: seven extra words (deployment-faithful frame sampling)"
profile["scope"] = ("Recorded clips sampled contiguously over the signing window, as the live camera "
                    "pipeline does; 11/16 unsupported signs were falsely accepted. Live-camera accuracy "
                    "unverified. Protocol changed 2026-10-18.")
profile["words"] = RESULTS
profile["note"] = ("2026-10-18: frame sampling changed from uniform to contiguous. Two test clips are "
                   "still untrackable (1 FOOD-class clip and 1 GO clip). Model and parameters unchanged; "
                   "per-word cutoffs were searched on validation and did not change the test result.")
ACCURACY.write_text(json.dumps(accuracy, indent=2) + "\n")

evaluation = json.loads(EVAL.read_text())
history = evaluation.get("protocolHistory", {})
history["uniformSampling-20261010"] = {
    "protocol": "30 frames sampled uniformly across the whole clip",
    "perWord": evaluation["perWord"],
    "expanded": evaluation["expanded"],
    "note": "Predates both the contiguous protocol and the current model file.",
}
evaluation.update(
    protocol=("Contiguous frame sampling over the signing window, matching the live camera pipeline. "
              "Model, prototypes and parameters unchanged from the uniform-sampling run. Two of the "
              "48 supported clips still produce no usable sequence."),
    protocolNote=("Per-word distance cutoffs were searched on validation only; no combination improved "
                  "the test result, so the shipped parameters were kept."),
    protocolHistory=history,
    perWord={word: {"total": value["total"], "correct": value["correct"]}
             for word, value in RESULTS.items()},
    expanded={"new": {"total": sum(v["total"] for v in RESULTS.values()),
                      "correct": sum(v["correct"] for v in RESULTS.values())},
              "negative": {"total": NEGATIVE["total"], "wrong": NEGATIVE["false"]}},
    untracked={"test": UNTACKED},
)
EVAL.write_text(json.dumps(evaluation, indent=2) + "\n")

print("expanded profile:", json.dumps(RESULTS))
total = sum(v["total"] for v in RESULTS.values())
correct = sum(v["correct"] for v in RESULTS.values())
print(f"total {correct}/{total} ({round(100*correct/total,1)}%)  false accepts {NEGATIVE['false']}/{NEGATIVE['total']}")
