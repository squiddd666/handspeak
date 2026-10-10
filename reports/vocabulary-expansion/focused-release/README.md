# Focused 11-word confirmation

**Failed; not deployed.** Frozen evaluation: 29/44 correct, zero wrong words,
15 misses and zero false accepts among 92 other-sign clips. NIGHT had zero
correct clips out of four, so the unchanged per-word coverage gate failed.

The 11 labels were selected after inspecting the preceding 17-label test.
That preceding test is now development evidence. This confirmation used new
recordings, with checkpoint, label mask and thresholds frozen before evaluation.
It samples existing held-out signer populations, not newly recruited people.

| Word | Correct / 4 |
| --- | ---: |
| CALL | 3 |
| FIND | 3 |
| FISH | 3 |
| HAVE | 3 |
| HOME | 4 |
| HUNGRY | 2 |
| MORNING | 1 |
| NIGHT | 0 |
| PAIN | 4 |
| SEE | 4 |
| SICK | 2 |

Removing NIGHT after viewing this result would require another frozen evaluation;
it would not turn this failed confirmation into an independent pass.
Browser camera integration and existing-vocabulary regression also remain unmet.

Results: `test-results.json`. Private run:
`/opt/handspeak-training/vocabulary-expansion-focused-release`.
