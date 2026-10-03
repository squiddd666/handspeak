"""Research-only clip-local stabilization of contiguous single-hand tracks.

Detector handedness can flicker. Use the majority slot within a close, contiguous
single-hand run; never bridge missing frames or rearrange two-hand detections.
This is a hypothesis to evaluate, not ground-truth hand identity correction.
"""
import math


def stabilize(row):
    frames = [list(f) for f in row['rawFrames']]
    run = []
    changed = 0

    def flush():
        nonlocal changed
        if not run:
            return
        counts = [sum(slot == side for _, slot, _ in run) for side in (0, 1)]
        # Ties use the first observation, preserving mirror equivariance.
        target = run[0][1] if counts[0] == counts[1] else int(counts[1] > counts[0])
        for index, slot, hand in run:
            if slot != target:
                frames[index] = [None, None]
                frames[index][target] = hand
                changed += 1
        run.clear()

    for index, frame in enumerate(frames):
        slots = [i for i, hand in enumerate(frame) if hand is not None]
        if len(slots) != 1:
            flush()
            continue
        slot = slots[0]; hand = frame[slot]
        if run:
            prior = run[-1][2][0]; current = hand[0]
            distance = math.hypot(current['x'] - prior['x'],
                                  (current['y'] - prior['y']) * row['imageAspect'])
            if distance >= .12:
                flush()
        run.append((index, slot, hand))
    flush()
    return dict(row, rawFrames=frames, stabilizedSlotFrames=changed)
