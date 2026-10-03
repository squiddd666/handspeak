# Sentence vocabulary experiment v6

Working directory: `/opt/handspeak-training/vocabulary-v6`, outside the served site. Run with the training virtual environment. Scripts retain this experiment’s fixed paths and import existing vocabulary/accuracy helpers. Archive/copy scripts into that private directory before running. Use a new directory and new reserved clips for future experiments; do not overwrite frozen artifacts or tune from this test set.

Order: prepare.py selects clips/downloads development only; extract.py extracts landmarks; fit.py selects parameters from validation and freezes the candidate; make_videos.py prepares attributed training examples; evaluate.py evaluates reserved clips and prior regression sets. Threshold selection uses validation coverage first, then an error penalty. See reports/vocabulary-v6/protocol-note.txt for the validation-based priority revision.

Four labels: FOOD, HUNGRY, LIKE, GO. 24 selected training, 8 validation, and 6 test clips per label, with distinct signer partitions. 59 of 96 training clips provided usable sequences. Seven extra words are opt-in; original six-word default stays unchanged. Sentence controls compose reviewed text and do not learn ASL grammar.
