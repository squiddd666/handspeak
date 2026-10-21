# SignBart compatibility test

**Result: failed — do not deploy this model.** Tested October 21, 2026 against
SignBart commit `1b7d3d1a1df11ee9147464143ea002d2b8688970`.

| Check | Result | Evidence |
|---|---|---|
| WLASL vocabulary order | Provisional | Official WLASL prefix lists were exported, but SignBart's original maps are absent. |
| ASL-Citizen mappings | Failed | The 2,731-label baseline map is reproducible; SignBart's smaller subset membership/order is undocumented. |
| ASL checkpoint downloads | Failed | All nine advertised WLASL and ASL-Citizen Google Drive IDs returned HTTP 404. |
| GitHub weight fallback | Failed | No releases or committed `.pth`, `.pt`, or `.safetensors` files exist. |
| Published source import | Failed | `model.py` uses top-level imports while `decoder.py` uses package-relative imports. |
| Published normalization | Failed | It sends one `(x,y)` point to a function that requires a group of points and raises `IndexError`. |
| Architecture smoke test | Conditional pass | After fixing imports in a disposable test copy, `(1,16,75,2)` produced finite `(1,100)` logits. The untrained model had 754,532 parameters. |
| License/reuse permission | Failed | The repository contains no license declaration. |

The architecture can execute after a small import repair, but recognition
compatibility cannot be tested without weights and exact class maps. A random
untrained forward pass is not recognition evidence. The generated vocabulary
files remain useful for catalog research, but must not be presented as live
camera support.

Integration can resume only after obtaining all of the following from the
author: an accessible checkpoint, its exact `label2id.json` and
`id2label.json`, the corrected preprocessing code used during training, and
permission to reuse the model. The candidate must then pass held-out
signer-independent accuracy, unsupported-motion false-match, real-camera, and
Android performance tests before deployment.
