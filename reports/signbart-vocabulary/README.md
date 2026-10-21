# SignBart dataset vocabulary export

Generated from the official dataset metadata available on this server. These
are gloss labels (class names), not proof that a live recognizer supports each
sign.

| File prefix | Labels | Ordering |
|---|---:|---|
| `wlasl-100` | 100 | First 100 entries in WLASL v0.3 |
| `wlasl-300` | 300 | First 300 entries in WLASL v0.3 |
| `wlasl-1000` | 1,000 | First 1,000 entries in WLASL v0.3 |
| `wlasl-2000` | 2,000 | Complete WLASL v0.3 gloss order |
| `asl-citizen-2731` | 2,731 | Alphabetical training-gloss order used by Microsoft's baseline loader |
| `combined-asl-glosses` | 3,572 | Case-insensitive union; 1,159 labels overlap |

Each vocabulary is provided as plain text, CSV, and JSON. JSON includes
`labels`, `label2id`, and `id2label`.

## Checkpoint compatibility warning

SignBart does not publish the `label2id.json` and `id2label.json` files used to
train its downloadable checkpoints. The WLASL prefix lists follow the standard
dataset order, but checkpoint compatibility must still be verified. SignBart
also does not document how its ASL-Citizen 100/200/400/1000 subsets were
selected, so this export intentionally does not invent maps for those subsets.
The complete 2,731-label ASL-Citizen map follows Microsoft's public baseline
loader, not a recovered SignBart checkpoint map.

Regenerate with `training/catalog/export_signbart_vocabularies.py` using the
official WLASL v0.3 JSON and ASL-Citizen training CSV. Training videos and
participant metadata are not copied into this report.

See `compatibility-test.md` and `compatibility-test.json` for the deployment
compatibility audit. The current result is failed; none of these vocabulary
exports has been enabled as a live recognition model.

`asl-only-readiness.md` records the ASL-only deployment decision and confirms
that the separate 100-label ASL-Citizen model already on the website is the
only ready experimental model in this review.
