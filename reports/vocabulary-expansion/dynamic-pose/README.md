# Dynamic-body training continuation

**Running; no new accuracy result or deployment yet.** The job reprocesses the
2,815 frozen development recordings, measures body landmarks at each of 60 sampled
frames, aligns the motion window, and trains the residual model with explicit
fingertip/body features. It preserves existing hand-detector thresholds and
sequence-quality rules. No reserved test recordings enter this pipeline.

Extraction caches, raw recordings and checkpoints stay outside the website.
Checkpoint verification and offline browser parity run after training. A passing
development screen still requires independent tests, ordinary-movement negatives
and live-camera integration checks. The script never deploys a model.

Check progress:

```bash
cat /opt/handspeak-training/vocabulary-expansion-dynamic-pose/job-status.json
systemctl status handspeak-dynamic-pose.service
journalctl -u handspeak-dynamic-pose.service -n 30 --no-pager
```

The transient service survives terminal/chat closure, but not reboot. If it stops,
inspect `job-status.json` and the service error before restarting. The same command
resumes verified extraction caches; changed inputs or code require a new experiment
directory. Accuracy failure is a completed experiment, not a successful release.

```bash
/opt/handspeak-training/venv/bin/python training/catalog/run_dynamic_pose_training.py \
  --baseline /opt/handspeak-training/vocabulary-expansion-joint50-separated \
  --output /opt/handspeak-training/vocabulary-expansion-dynamic-pose \
  --report reports/vocabulary-expansion/dynamic-pose --workers 3
```

The extraction protocol freezes source hashes, model assets, code and detector
settings. Source snapshots are retained in the private experiment directory.
