"""Freeze a development feature-window experiment without changing quality gates."""
import argparse
import hashlib
import json
from pathlib import Path
import motion_window
import stable_hand_slots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stabilize-slots', action='store_true')
    parser.add_argument('--keep-full-window', action='store_true')
    args = parser.parse_args()
    baseline = json.loads((args.baseline / 'protocol.json').read_text())
    source = Path(baseline['source'])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != baseline['sourceSha256']:
        raise ValueError('Source differs from frozen baseline')
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / 'development-features.json'
    if output.exists():
        raise FileExistsError('Use a new feature directory; never overwrite a frozen input')
    rows = json.loads(source.read_text())
    if any(r['split'] not in ('train', 'val') for r in rows):
        raise ValueError('Only development rows are allowed')
    updated = [stable_hand_slots.stabilize(r) if args.stabilize_slots else r for r in rows]
    if not args.keep_full_window:
        updated = [motion_window.align_window(r) for r in updated]
    if any(a.get('sequence') != b.get('sequence') for a, b in zip(rows, updated)):
        raise ValueError('Preprocessing changed a sequence-quality decision')
    result = dict(source=str(source), sourceSha256=digest,
                  implementationSha256=hashlib.sha256(Path(motion_window.__file__).read_bytes()).hexdigest(),
                  rows=len(rows), changedWindows=sum(len(a['rawFrames']) != len(b['rawFrames']) for a,b in zip(rows,updated)),
                  originalFrames=sum(len(r['rawFrames']) for r in rows),
                  alignedFrames=sum(len(r['rawFrames']) for r in updated),
                  fullWindowRetained=args.keep_full_window, slotsStabilized=args.stabilize_slots,
                  slotImplementationSha256=hashlib.sha256(Path(stable_hand_slots.__file__).read_bytes()).hexdigest() if args.stabilize_slots else None,
                  stabilizedSlotFrames=sum(r.get('stabilizedSlotFrames', 0) for r in updated),
                  stabilizedClips=sum(r.get('stabilizedSlotFrames', 0) > 0 for r in updated),
                  qualityDecisionsUnchanged=True, independentTestOpened=False, deployed=False,
                  note='Temporal features only. Optional windowing follows encodeMotion; optional slot stabilization changes only single-hand slot placement. Original frames/trackedFrames metadata describes original extraction.')
    tmp = output.with_suffix('.partial')
    with tmp.open('w') as stream:
        json.dump(updated, stream, separators=(',', ':'))
    tmp.replace(output)
    result['outputSha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    (args.output / 'window-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (args.output / 'labels.json').write_text(json.dumps(baseline['labels']) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
