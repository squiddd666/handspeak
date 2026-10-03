"""Metadata-only WLASL/MS-ASL crosswalk; no recognition or availability claims."""
import collections
import hashlib
import json
from pathlib import Path
import re
import zipfile
import csv

SITE = Path(__file__).resolve().parents[2]
SOURCE = Path('/opt/handspeak-training/vocabulary-source-audit/WLASL_v0.3.json')
normalize = lambda value: re.sub('[^A-Z0-9]', '', value.upper())


def main():
    data = json.loads(SOURCE.read_text())
    baseline = json.loads((SITE / 'reports/vocabulary-expansion/all-201-readiness.json').read_text())
    index = {normalize(row['gloss']): row for row in data}
    entries = []
    for item in baseline['entries']:
        candidate = index.get(normalize(item['word']))
        if candidate is None:
            continue
        instances = candidate['instances']
        splits = {split: {str(r['signer_id']) for r in instances if r['split'] == split}
                  for split in ('train', 'val', 'test')}
        overlap = (splits['train'] & splits['val']) | (splits['train'] & splits['test']) | (splits['val'] & splits['test'])
        entries.append(dict(
            dataset='WLASL', mapping='normalized-text',
            word=item['word'], candidateGloss=candidate['gloss'],
            previousStatus=item.get('baselineStatus', item['status']), metadataClips=len(instances),
            splitCounts=dict(collections.Counter(r['split'] for r in instances)),
            signerCounts={s: len(v) for s, v in splits.items()},
            signerIdsSharedAcrossSplits=sorted(overlap),
            status='metadata-candidate-only', videoAvailabilityVerified=False,
            semanticMappingVerified=False, trained=False,
            nextStep='Review the sign meaning and dataset terms, verify source-video '
                     'availability, reserve signer-disjoint partitions and duplicates '
                     'across all datasets, then extract training data.'))
    msasl_path = SOURCE.parent / 'MS-ASL.zip'
    with zipfile.ZipFile(msasl_path) as archive:
        classes = json.loads(archive.read('MS-ASL/MSASL_classes.json'))
        synonyms = json.loads(archive.read('MS-ASL/MSASL_synonym.json'))
        msasl_rows = {s: json.loads(archive.read(f'MS-ASL/MSASL_{s}.json'))
                      for s in ('train', 'val', 'test')}
    class_index = {normalize(label): i for i, label in enumerate(classes)}
    for item in baseline['entries']:
        label_id = class_index.get(normalize(item['word']))
        mapping = 'normalized-text'
        if label_id is None:
            candidates = {class_index[normalize(s)] for group in synonyms
                          if normalize(item['word']) in {normalize(s) for s in group}
                          for s in group if normalize(s) in class_index}
            if len(candidates) == 1:
                label_id = candidates.pop()
                mapping = 'dataset-synonym-candidate'
        if label_id is None:
            continue
        matched = {s: [r for r in rows if r['label'] == label_id]
                   for s, rows in msasl_rows.items()}
        signers = {s: {str(r['signer_id']) for r in rows} for s, rows in matched.items()}
        overlap = (signers['train'] & signers['val']) | (signers['train'] & signers['test']) | (signers['val'] & signers['test'])
        entries.append(dict(dataset='MS-ASL', mapping=mapping, word=item['word'],
            candidateGloss=classes[label_id], previousStatus=item.get('baselineStatus', item['status']),
            metadataClips=sum(map(len, matched.values())),
            splitCounts={s: len(rows) for s, rows in matched.items()},
            signerCounts={s: len(v) for s, v in signers.items()},
            signerIdsSharedAcrossSplits=sorted(overlap), status='metadata-candidate-only',
            videoAvailabilityVerified=False, semanticMappingVerified=False, trained=False,
            nextStep='Verify video availability and sign meaning, review terms, and '
                     'reserve signer-disjoint partitions across all sources before training.'))
    citizen_root = Path('/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits')
    citizen = {s: list(csv.DictReader((citizen_root / (s + '.csv')).open()))
               for s in ('train', 'val', 'test')}
    existing_words = {r['word'] for r in entries}
    for item in baseline['entries']:
        if item['word'] in existing_words or item.get('baselineStatus', item['status']) != 'needs-verified-training-source':
            continue
        variants = sorted({r['Gloss'] for r in citizen['train']
                           if re.fullmatch(re.escape(normalize(item['word'])) + r'[0-9]+', normalize(r['Gloss']))})
        if not variants:
            continue
        matched = {s: [r for r in rows if r['Gloss'] in variants] for s, rows in citizen.items()}
        signers = {s: {r['Participant ID'] for r in rows} for s, rows in matched.items()}
        overlap = (signers['train'] & signers['val']) | (signers['train'] & signers['test']) | (signers['val'] & signers['test'])
        entries.append(dict(dataset='ASL Citizen', mapping='numbered-variant-candidate',
            word=item['word'], candidateGloss=' | '.join(variants),
            previousStatus=item.get('baselineStatus', item['status']),
            metadataClips=sum(map(len, matched.values())), splitCounts={s: len(v) for s, v in matched.items()},
            signerCounts={s: len(v) for s, v in signers.items()}, signerIdsSharedAcrossSplits=sorted(overlap),
            status='metadata-candidate-only', videoAvailabilityVerified=False, semanticMappingVerified=False,
            trained=False, nextStep='Verify meanings of numbered variants and permitted use before combining or training.'))
    newly_found = sorted({r['word'] for r in entries if r['previousStatus'] == 'needs-verified-training-source'})
    previously_missing = [r['word'] for r in baseline['entries'] if r.get('baselineStatus', r['status']) == 'needs-verified-training-source']
    remaining = [word for word in previously_missing if word not in newly_found]
    result = dict(source='https://github.com/dxli94/WLASL',
                  metadataUrl='https://raw.githubusercontent.com/dxli94/WLASL/master/start_kit/WLASL_v0.3.json',
                  metadataSha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  additionalMetadataSource='https://download.microsoft.com/download/3/c/a/3ca92c78-1c4a-4a91-a7ee-6980c1d242ec/MS-ASL.zip',
                  additionalMetadataSha256=hashlib.sha256(msasl_path.read_bytes()).hexdigest(),
                  citizenVariantMetadataSha256={s: hashlib.sha256((citizen_root / (s + '.csv')).read_bytes()).hexdigest() for s in citizen},
                  metadataOnly=True, matchedCatalogEntries=len({r['word'] for r in entries}),
                  additionalCandidatesForPreviouslyMissingWords=newly_found,
                  stillWithoutExactTextCandidate=remaining, entries=entries)
    root = SITE / 'reports/vocabulary-expansion'
    (root / 'additional-source-candidates.json').write_text(json.dumps(result, indent=2) + '\n')
    (root / 'additional-source-candidates.md').write_text(
        '# Additional source candidates — metadata only\n\n'
        f"WLASL, MS-ASL, and ASL Citizen numbered-variant metadata have candidates for {len({r['word'] for r in entries})} catalog entries, "
        f"including **{len(newly_found)} of the 66** previously missing local-source entries. "
        'No videos were downloaded or trained in this source audit. These are source leads, '
        'not verified semantic mappings or enabled recognition words.\n\n'
        'New leads: ' + ', '.join(newly_found) + '.\n\n'
        f"The remaining {len(remaining)} entries without a text/synonym candidate in this comparison: "
        ', '.join(remaining) + '.\n\n'
        'Counts reflect metadata, not accessible videos. Check signer identities across '
        'partitions and datasets, unknown IDs, duplicate clips, regional variants, and '
        'ambiguous English glosses before training. Source clips and model distribution '
        'must comply with the dataset terms; no new source assets are published here.\n\n'
        'Source: [official WLASL repository](https://github.com/dxli94/WLASL), '
        '[dataset description and C-UDA license reference](https://github.com/dxli94/WLASL/blob/master/index.md). '
        'Additional source: [Microsoft MS-ASL catalog](https://microsoft.github.io/data-for-society/dataset?d=MS-ASL-American-Sign-Language-Dataset). '
        'Numbered variants: [ASL Citizen](https://www.microsoft.com/en-us/research/project/asl-citizen/). '
        'The companion JSON records the metadata hash and per-word partition counts.\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}, indent=2))


if __name__ == '__main__':
    main()
