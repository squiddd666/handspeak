# Sentence-chip control check

`check_chips.py` copies `experience-ui.js` from the repository into this directory, serves
the stub `index.html` on 127.0.0.1, and drives the chip list in headless Chromium:

- every chip exposes an edit control and a remove control with descriptive labels
- arrow keys move focus between chips, `Home`/`End` jump, `Delete`/`Backspace` removes
- removal keeps focus inside the chip list and announces the change
- clearing every word restores the empty state and updates the progress status

Run with the training environment:

```
/opt/handspeak-training/venv/bin/python training/ux/chips/check_chips.py
```

No camera, MediaPipe, network or database access. Expected result: `RESULT: PASS`.
