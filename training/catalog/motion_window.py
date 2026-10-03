"""Align temporal features to the same visible run used by encodeMotion.

This changes feature windows, never the stored sequence-quality decision. Short
internal tracking gaps are interpolated; separate movements are never joined.
"""
import copy


def align_window(row):
    frames = copy.deepcopy(row['rawFrames'])
    visible = [i for i, f in enumerate(frames) if any(h is not None for h in f)]
    if not visible:
        return dict(row)
    start, end = visible[0], visible[-1] + 1
    frames = frames[start:end]
    body = row.get('body', [None] * len(row['rawFrames']))[start:end]
    if len(body) != len(frames):
        raise ValueError('Body and hand frame counts differ')
    for side in (0, 1):
        i = 1
        while i < len(frames) - 1:
            if frames[i][side] is not None or frames[i - 1][side] is None:
                i += 1
                continue
            nxt = i
            while nxt < len(frames) and frames[nxt][side] is None:
                nxt += 1
            if nxt == len(frames) or nxt - i > 2:
                i += 1
                continue
            a, b = frames[i - 1][side], frames[nxt][side]
            for j in range(i, nxt):
                t = (j - i + 1) / (nxt - i + 1)
                frames[j][side] = [{k: p[k] + (q[k] - p[k]) * t for k in ('x', 'y', 'z')}
                                   for p, q in zip(a, b)]
            i = nxt + 1
    runs = []
    for i, frame in enumerate(frames):
        if not any(h is not None for h in frame):
            continue
        if not runs or i - runs[-1]['end'] > 3:
            runs.append(dict(start=i, end=i, count=0))
        runs[-1]['end'] = i
        runs[-1]['count'] += 1
    strongest = max(runs, key=lambda r: r['count'])
    if strongest['count'] >= 8 and strongest['count'] >= .7 * sum(r['count'] for r in runs):
        a, b = strongest['start'], strongest['end'] + 1
        frames, body = frames[a:b], body[a:b]
        start += a
        end = start + len(frames)
    result = dict(row, rawFrames=frames, body=body, temporalWindow=[start, end])
    if 'timestamps' in row:
        result['timestamps'] = row['timestamps'][start:end]
    return result
