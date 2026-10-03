# Expanded training experiment

**Status: withheld. No new model deployed.**

Words: THIRSTY, HOT, SICK, READ, GIVE, CALL, FIND, NOW, TOMORROW, MILK.

| Model | Correct | Wrong word | Missed | Other-sign false accepts |
| --- | ---: | ---: | ---: | ---: |
| Temporal | 23/40 | 0 | 17 | 3/154 |
| DTW | 10/40 | 0 | 30 | 0/154 |

Training: 828 usable clips out of 927. Validation: 194 clips.

Development validation data previously used in research. Temporal features use center-frame body references where visible, otherwise wrist-centered fallback. Whole clips, not live capture. No test set is opened by this script.

Validation is screening only. Require a new untouched signer test, real ordinary-movement negatives, comparison with current models, and real-time browser capture tests before deployment.

These are validation model-selection results, not independent accuracy or real webcam measurements. Other-sign negatives do not cover ordinary hand movements. The first 10-word experiment and this experiment share validation recordings; changes are development comparisons only.

Body positions use a single center-frame reference. New training clips sample 60 frames; cached clips retain their earlier sampling. These changes mean any difference cannot be attributed solely to additional training data.

Raw clips and checkpoints remain outside the served website. Source: [PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html), Georgia Tech and DPAN, CC BY 4.0.

The complete 201-entry recognition expansion remains unfinished. Entries without verified labeled sources require data acquisition and semantic review; phrases cannot be mapped to isolated signs by text alone.

This experiment sets `--negative-weight 10`: other-sign classification errors receive ten times the original class loss weight. The unchanged DTW baseline is reused from batch2 after verifying identical data hashes and labels.
