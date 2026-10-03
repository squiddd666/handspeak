# Dense-frame recovery experiment

The first extraction pass produced usable sequences for 553/779 development clips. Retrying its 226 failures at up to 60 sampled frames recovered 150 additional sequences: the final development set contains 524 usable training and 179 usable validation sequences. Test recovery was run only after fitting and freezing models; it recovered 28 more test sequences.

Detector confidence, minimum hand-size gates, browser encoding, signer partitions, and source recordings were retained. The initial recovery pass attempted to sample more frames from the original recordings; short clips in the initial attempt could be temporally upsampled; see the final audit below. Usable clips from the original pass were retained unchanged.

**No category replacement was selected.** Some candidates improved recall or rejection separately, but none met the combined improvement rules. The six-word default model was not replaced. The baseline remains 46/194 correct when counting the untrained BED clips as misses, with one wrong supported-label suggestion and 116 false suggestions in 2,774 repeated category-negative comparisons.

See `validation-report.json`, `regression.json`, and `summary.json`. This is a paired comparison on previously evaluated recordings, not an independent accuracy benchmark. Better offline tracking coverage does not demonstrate higher live-camera accuracy.


**Final sampling audit:** the initial recovery worker temporally upsampled some short clips. Its recovery counts and v8/v9 results are archived diagnostics, not evidence of improved accuracy. See [sampling issue and correction](../vocabulary-v9/SAMPLING-ISSUE.md). The new category models remain withheld.
