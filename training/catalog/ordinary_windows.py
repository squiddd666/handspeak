"""Generate real-timestamp subwindows without manufacturing detector frames."""
import math


def window_rows(row, width_ms=3000, max_windows=4):
    if width_ms <= 0 or max_windows < 1:
        raise ValueError('Positive window size and count required')
    times = row.get('timestamps', [])
    frames = row['rawFrames']
    if len(times) != len(frames) or any(not math.isfinite(t) for t in times):
        raise ValueError('Missing or invalid frame timestamps')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Timestamps must increase')
    if len(times) < 2 or times[-1] - times[0] <= width_ms:
        return []
    body = row.get('body', [None] * len(frames))
    if len(body) != len(frames):
        raise ValueError('Mismatched body length')
    final_start = times[-1] - width_ms
    count = min(max_windows, max(2, math.ceil((times[-1] - times[0]) / width_ms)))
    starts = [times[0] + (final_start - times[0]) * i / (count - 1) for i in range(count)]
    result = []
    for start in starts:
        ids = [i for i, t in enumerate(times) if start <= t <= start + width_ms]
        if len(ids) < 2:
            continue
        lo, hi = ids[0], ids[-1] + 1
        result.append(dict(row, rawFrames=frames[lo:hi], body=body[lo:hi],
                           timestamps=times[lo:hi], sequence=None,
                           frames=hi-lo, trackedFrames=sum(any(h is not None for h in f) for f in frames[lo:hi]),
                           windowMs=[times[lo], times[hi-1]],
                           exampleId=f"{row['sha256']}:{times[lo]}:{times[hi-1]}"))
        result[-1].pop('temporalWindow', None)
    return result
