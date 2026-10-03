"""Additional research leads, never automatic relabeling or model promotion.

Use SignBank's lexical English translations, not ASL-LEX nondominant naming
responses: the latter include participant guesses that can name unrelated signs.
Reference videos from ASL-LEX are not downloaded or licensed by this script.
"""
import collections
import csv
import hashlib
import re


def normalize(value):
    return re.sub('[^A-Z0-9]', '', value.upper())


def translation_matches(word, row):
    return normalize(word) in {
        normalize(value.strip()) for value in row.get('SignBankEnglishTranslations', '').split(',')
        if value.strip()
    }


def source_leads(words, citizen, root):
    lex_path = root / 'asl-lex-metadata.csv'
    with lex_path.open(encoding='latin-1', newline='') as stream:
        lex = list(csv.DictReader(stream))
    glosses = collections.defaultdict(set)
    for row in citizen['train']:
        glosses[normalize(row['Gloss'])].add(row['Gloss'])
    entries = []
    for word in words:
        for row in lex:
            if not translation_matches(word, row):
                continue
            variants = glosses.get(normalize(row['EntryID']), set())
            if not variants:
                continue
            matched = {s: [r for r in rows if r['Gloss'] in variants] for s, rows in citizen.items()}
            signers = {s: {r['Participant ID'] for r in rows} for s, rows in matched.items()}
            entries.append(dict(dataset='ASL Citizen via ASL-LEX/SignBank metadata',
                word=word, candidateGloss=' | '.join(sorted(variants)),
                mapping='lexical-translation-candidate', previousStatus='needs-verified-training-source',
                metadataClips=sum(map(len, matched.values())),
                splitCounts={s: len(rows) for s, rows in matched.items()},
                signerCounts={s: len(ids) for s, ids in signers.items()},
                signerIdsSharedAcrossSplits=sorted((signers['train'] & signers['val']) |
                    (signers['train'] & signers['test']) | (signers['val'] & signers['test'])),
                evidence=dict(entryID=row['EntryID'], field='SignBankEnglishTranslations',
                              translations=row['SignBankEnglishTranslations']),
                status='metadata-candidate-only', videoAvailabilityVerified=False,
                semanticMappingVerified=False, trained=False,
                nextStep='Review the lexical variant in context with an ASL reviewer; translations '
                    'may collide with other catalog words. Do not merge, relabel, or enable from metadata. '
                    'Use ASL Citizen terms for any eventual recordings, not ASL-LEX reference videos.'))
    hashes = {lex_path.name: hashlib.sha256(lex_path.read_bytes()).hexdigest()}
    rejected = {}
    corpus = []
    for path in sorted((root / 'signbank').glob('*.csv')):
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        malformed = 0
        with path.open(newline='') as stream:
            for row in csv.DictReader(stream):
                if None in row or any(value is None for value in row.values()):
                    malformed += 1
                    continue
                corpus.append((path.name, {k.lower(): v for k, v in row.items()}))
        rejected[path.name] = malformed
    for word in words:
        matched = []
        for filename, row in corpus:
            # Main entry labels only: do not strip compounds/negation qualifiers.
            if normalize(row.get('main entry gloss label', '')) == normalize(word):
                matched.append((filename, row))
        if not matched:
            continue
        entries.append(dict(dataset='Rutgers/BU SignBank', word=word, candidateGloss=word,
            mapping='main-entry-text-candidate', previousStatus='needs-verified-training-source',
            metadataClips=len(matched), splitCounts=None,
            signerCounts=None, signerIdsSharedAcrossSplits=None,
            sourceFiles=dict(collections.Counter(name for name, _ in matched)),
            status='metadata-candidate-only', videoAvailabilityVerified=False,
            semanticMappingVerified=False, trained=False,
            nextStep='Resolve signer identities and licensing before any downloads. Clip/session IDs '
                'are not signer IDs. Verify annotation timing, buffered clips, and slowed playback. '
                'Do not infer signer-disjoint partitions or publish videos from these metadata rows.'))
    return entries, dict(metadataSha256=hashes, malformedRowsExcluded=rejected,
        aslLexMetadataTerms='CC BY-NC 4.0; ASL-LEX reference videos excluded; metadata only.',
        aslLexTermsUrl='https://asl-lex.org/download.html',
        signBankMetadataUrl='https://dai.cs.rutgers.edu/asllvd/signbank/',
        signBankTermsUrl='https://www.bu.edu/asllrp/av/dai-asllvd.html',
        restrictions='Source licensing must be checked for each collection and intended use. '
            'No reference videos downloaded; translations are unverified candidates, not training labels.')
