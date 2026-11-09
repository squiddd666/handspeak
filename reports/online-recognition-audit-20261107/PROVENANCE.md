# Setup provenance and failure triage

The original frozen protocol preceded all predictions. Native extraction and classification each ran once for all 76 clips. Browser playback/capture/inference each ran once for all 76 clips after two setup-only failures. No result-driven capture or classifier retry occurred.

1. Original setup: Node v24 undici asserted on an unconsumed HTTP readiness body. Chrome was not launched; there were no video requests or captured outcomes. The failed launch log and empty ledger are retained in `C:\Users\Squid\Desktop\capstone\hs-eval\online-recognition-audit-20261107`.
2. Transport v2: Chrome failed to download the unchanged Holistic packed asset from jsDelivr with `net::ERR_QUIC_PROTOCOL_ERROR`. Detectors never initialized, no source videos were requested, and its ledger remained empty. Boot diagnostics are retained in `C:\Users\Squid\Desktop\capstone\hs-eval\online-recognition-audit-20261107\browser-transport-v2\boot-diagnostics.json`.
3. Transport v3: added only `--disable-quic` to the developer-owned Chrome launch arguments. Frozen classifiers, weights, captures and recording durations remained byte-identical. All 76 captures/outcomes were retained, including the failed warm-up. The native evidence was copied without rerunning it; hashes and original protocol are recorded in `C:\Users\Squid\Desktop\capstone\hs-eval\online-recognition-audit-20261107\browser-transport-v3\native-evidence-receipt.json`.

## Observed bottleneck

**74/75 completed browser captures had fewer than 12 manual-stream frames**, the frozen manual encoder's minimum. Median time between paired samples was **916.5 ms**. Only **5/76** browser attempts produced a usable body-candidate tensor. The one warm-up failure remains a no-match outcome, not an omitted take.

The driver uses SwiftShader software rendering. This demonstrates a throughput/input-quality failure in this isolated configuration; it is not proof that all user hardware has the same bottleneck. Matching detector inputs is not sufficient evidence of a useful recording.

Native candidate input preparation accepted **67/69** positive clips, but **52** valid positive inputs were still rejected by the frozen classifier. Its single wrong acceptance was **SICK → HOME**. Independent native manual modes also showed substantial wrong/outside-vocabulary accepts; their results must not be merged into an oracle route.

## Repair priority

First address capture throughput/source readiness with independent development fixtures, then address classifier rejection/confusion using separate development recordings. Do not lower gates, train references or calibrate using this audit cohort. Full production-app routing, full-198 regression and truly new-signer validation remain outstanding.

`triage.json` contains the failure decomposition; `verification.json` contains post-run hash/order/metric verification. The audit browser/server exited and no listeners remained on the owned loopback ports 8009/9227; no owned profile/server process remained.
