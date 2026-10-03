"""Assemble a joint catalog experiment from cached development clips only.

This does not enable words or read held-out test recordings. Existing vocabulary
outside the target catalog is used as other-sign negatives for this candidate;
it must not replace the existing recognizers without a separate regression test.
"""
import argparse
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = [
    Path('/opt/handspeak-training/vocabulary-expansion-batch2/body-development-features.json'),
    Path('/opt/handspeak-training/accuracy-v4/development-features.json'),
]


def assemble(sources, catalog):
    selected = {}
    provenance = []
    for source in sources:
        data = json.loads(source.read_text())
        provenance.append(dict(path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        for row in data:
            if row['split'] not in ('train', 'val'):
                raise ValueError('Test recordings cannot enter development data')
            for field in ('sha256', 'participant', 'label'):
                if not row.get(field):
                    raise ValueError(f'Missing clip identity: {field}')
            prior = selected.get(row['sha256'])
            if prior:
                if any(str(prior[k]) != str(row[k]) for k in ('split', 'label', 'participant')):
                    raise ValueError('Duplicate recording has conflicting partition or annotation')
                continue  # Prefer the first (expanded, body-enriched) source.
            selected[row['sha256']] = row
    rows = list(selected.values())
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'val']
    if {str(r['participant']) for r in train} & {str(r['participant']) for r in val}:
        raise ValueError('Train/validation signers overlap')
    available = {r['label'] for r in train if r.get('sequence') is not None}
    labels = sorted(available & {r['label'] for r in catalog['items']})
    return rows, labels, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    catalog = json.loads((SITE / 'models/motion-vocabulary.json').read_text())
    rows, labels, sources = assemble(DEFAULT_SOURCES, catalog)
    args.output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        'development-features.json': rows,
        'labels.json': labels,
        'assembly.json': dict(sources=sources, targetWords=len(labels), clips=len(rows),
            negativeLabels=sorted({r['label'] for r in rows} - set(labels)),
            missingCatalogWords=sorted({r['label'] for r in catalog['items']} - set(labels)),
            limitations='Previously inspected development data only; mixed hand sampling and '
                'center-frame/dynamic body extraction. Existing non-target signs are '
                'negatives for this research candidate, not removed from the website. '
                'No ordinary-motion negatives or live-camera evaluation. No deployment.'),
    }
    for name, value in artifacts.items():
        path = args.output / name
        if path.exists() and json.loads(path.read_text()) != value:
            raise ValueError(f'Existing {name} differs; choose a fresh output directory')
    for name, value in artifacts.items():
        path = args.output / name
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, separators=(',', ':')) + '\n')
        temporary.replace(path)
    print(json.dumps(artifacts['assembly.json'], indent=2))


if __name__ == '__main__':
    main()
