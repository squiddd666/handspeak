# Broader-negative training experiment

After recovering tracking failures, this experiment broadened the negative training pool to cover every available requested source label outside a category (up to 96 such references plus 18 references from the older vocabulary). Validation includes all new validation recordings, not just a small early subset of out-of-category labels.

For each category, the original model and candidate were compared on the same recovered validation inputs. Candidate parameters were selected to increase correct matches without exceeding the original model's wrong-label or unsupported-suggestion counts. Qualified models were frozen, hashed, and tested on the previously evaluated v7 regression clips, with the same dense recovery used by v8. Categories that failed validation did not receive a new candidate test; their baseline results remain unchanged in the report.

**No replacement passed the complete gate.** The final baseline remains 46/194 correct across the 49 downloaded requested labels (48 have enough usable references in the initial model), one wrong supported-label suggestion, and 116 false suggestions across 2,774 repeated out-of-category comparisons. This is not high accuracy. No default or category model is described as improved by these experiments.

The separate six-word attempt also failed paired validation: no tested parameter choice improved the original 47/84 correct count without exceeding its error counts. Its broader validation set exposed 108/220 unsupported false suggestions from the original default model. The candidate was not sent to a further test or deployed. See `core-validation.json` and `core-regression.json`.

The development recovery produced 150 additional usable sequences; test recovery added 28. More usable data did not establish a reliable classifier. The current hand-only encoding centers the movement and has no face/shoulder-relative position features; this can discard useful sign-location information. Addressing that limitation is a future experiment, not a demonstrated solution. The earlier temporal-model study also remains unpromoted.

## Interpretation and limits

- The 200-entry website catalog is a learning library, not a claim that all entries are pretrained.
- The 14 category models are research artifacts only and are withheld from the live site. Per-word recorded results are displayed, including zero-match outcomes. Automatic-capture replay missed all four fixed examples (BROTHER, BOOK, CAR, MILK), with no wrong suggestions or repeats.
- Positive test sources were held out from fitting, but these follow-up experiments reused previously inspected recordings. No independent high-accuracy claim is made.
- Negative totals count repeated comparisons across categories, not distinct videos. Cached development examples can occur in both older and newly collected negative pools; validation counts are comparison counts, not a claim of unique independent observations.
- There is no ordinary non-sign movement dataset or physical-webcam user study in this run. Real-time playback checks are reported separately and are not human-signing accuracy benchmarks.
- Default six-word, older extra-word, and static-letter model files remain byte-for-byte unchanged.


**Final sampling audit:** the initial recovery worker temporally upsampled some short clips. Its recovery counts and v8/v9 results are archived diagnostics, not evidence of improved accuracy. See [sampling issue and correction](../vocabulary-v9/SAMPLING-ISSUE.md). The new category models remain withheld.
