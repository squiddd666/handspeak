# Missing-landmark augmentation correction

**Research only; no deployment or demonstrated accuracy improvement yet.**

The preceding dynamic-body candidate failed: 135/210 correct, eight wrong,
67 missed, three false accepts among 90 other-sign clips. Its Python/Chromium
parity passed, so no conversion discrepancy was found in those checks.

The residual trainer added noise to every feature, including detection flags,
missing-hand zeros, and the local wrist coordinates that must remain zero.
`--masked-augmentation` preserves these invariants and jitters only coordinates
for present landmarks. It also keeps hand/body scale nonnegative. The default
legacy path remains available for comparison; previous source snapshots remain
archived. Time-warp interpolation is unchanged, including fractional visibility
at detection transitions. Eight model/feature tests passed.

This controlled retraining keeps the same dynamic-body features, 50 targets,
seven rejection labels, train/validation signers, seeds, epochs, threshold grid
and accuracy gate. It does not open held-out media or lower rejection thresholds
to force acceptance. Code snapshots and hashes are archived privately.

Other unresolved evidence:

- SHOWER has only eight usable training clips from nine recordings/five signers.
- ROOM lost tracking on one of four validation clips.
- FINISH lost tracking on four of fourteen validation clips.
- SPEAK has 47 usable training clips but no accepted correct validation result.

These are coverage/tracking/classification issues, not proof that the augmentation
change alone will fix accuracy. Repeated development screening is not independent
accuracy. Passing candidates still need fresh recorded-video/OBS evaluation,
ordinary-movement negatives and integration/regression checks. No new-person or
physical-webcam claim is supported by recorded playback.

Check `job-status.json` here or run:

```bash
systemctl status handspeak-masked-training.service
journalctl -u handspeak-masked-training.service -n 10 --no-pager
```

The managed run trains, reloads/verifies the winning checkpoint, then checks
browser parity. It never changes production. It survives chat/terminal closure
but not a server reboot.
