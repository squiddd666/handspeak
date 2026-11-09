# Recorded word-accuracy coverage

All **198 recognition labels** now have a recorded per-word benchmark available
to Watch & Learn and the vocabulary library. This is **coverage of results**,
not a claim that 198 words pass an accuracy threshold or form one active model.

The existing default, extra, five-word, BABY, and category results are preserved.
The missing full-100 and Beginner-79 counts were recovered from existing local
evaluation reports, including low-scoring words instead of filtering to a
previous "ready" subset.

* Full-100: **732/1,157 reported attempts** correct. **984** attempts produced a
  prediction; tracking failures remain in each word's denominator. This differs
  from the old 74.4% headline, which divides by answered clips only. Full mode
  is not the gated core/extended benchmark.
* Beginner-79: **505/677 held-out extracted test clips** correct. The selected
  checkpoint is `beginner-need79-v1.pt`. The three GOOD greeting labels were
  tested on their isolated dataset components, not complete greeting sequences.

These are archived recorded-test measurements, **not live-camera accuracy** or
confidence in a current prediction. Reference-video/virtual-camera smoke checks
must be reported separately and must never replace these benchmark counts.

`provenance.json` records source-report hashes and checkpoint identities. The
full ensemble's four tensor-state hashes match the evaluated snapshot union;
the Beginner checkpoint is pinned to the identity used by its report. Raw clips,
participant records, and feature caches are not copied into this report folder.

Rebuild locally with the project's PyTorch interpreter:

```powershell
python scripts/publish_motion_accuracy.py --eval-dir ../hs-eval
```

The publisher refuses incomplete or inconsistent counts and mismatched model
identities. It does not train models, change thresholds, start a camera, or
modify the database.
