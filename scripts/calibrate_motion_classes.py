"""Validation-only class-conditional gates with unchanged error budgets.

Sparse classes keep the global fallback. A class can relax its threshold only
with at least three accepted correct validation recordings, and never increases
its known-word errors or unsupported false accepts over the global policy.
No Watch/test recordings or selected practice labels are consulted.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from asl_model_tools import digest
from calibrate_motion_models import CORE, EXTRA, summarize


def fit_classes(probabilities, expected, labels, names, baseline, minimum_support=3):
    p = np.asarray(probabilities, dtype=float)
    valid = np.isfinite(p).all(1)
    selected = [labels.index(n) for n in names]
    q = np.nan_to_num(p, nan=0)[:, selected]
    mass = q.sum(1);q /= np.maximum(mass[:, None], 1e-15)
    ranking = np.argsort(q, axis=1)[:, ::-1]
    score = q[np.arange(len(q)), ranking[:, 0]]
    margin = score - (q[np.arange(len(q)), ranking[:, 1]] if len(names) > 1 else 0)
    predicted = np.asarray(names)[ranking[:, 0]]
    known = np.isin(expected, names);correct = predicted == expected
    keys = ('minScore', 'minMargin', 'minVocabularyMass')
    fallback = {k: baseline.get(k, 0) for k in keys}
    def accepts(policy):
        return valid & (score >= policy['minScore']) & (margin >= policy['minMargin']) & (mass >= policy['minVocabularyMass'])
    accepted = accepts(fallback);old = accepted.copy();policies = {};audit = {}
    grid = [0, .05, .1, .15, .2, .25, .3, .35, .4, .45, .5, .55, .6, .65, .7, .75, .8, .85, .9, .95, 1.000001]
    for name in names:
        members = valid & (predicted == name)
        original = summarize(correct[members], old[members], known[members])
        # Require multiple correct examples to support a relaxation. Do not
        # estimate permissive thresholds from just one favorable performance.
        if int((members & correct & known).sum()) < minimum_support:
            continue
        best = None
        for gate in sorted(set(grid + [fallback['minScore']])):
            for gap in sorted(set([0, .02, .05, .1, .15, .2, .25, .3, .4, .5, fallback['minMargin']])):
                candidate = {**fallback, 'minScore': gate, 'minMargin': gap}
                a = accepts(candidate)
                metrics = summarize(correct[members], a[members], known[members])
                if metrics['wrong'] > original['wrong'] or metrics['negativeFalse'] > original['negativeFalse']:
                    continue
                if metrics['correct'] < minimum_support or metrics['correct'] < original['correct']:
                    continue
                # Prefer small departures when operating counts tie.
                departure = abs(gate - fallback['minScore']) + abs(gap - fallback['minMargin'])
                key = (metrics['correct'], -metrics['wrong'], -metrics['negativeFalse'], -departure)
                if best is None or key > best[0]:best = (key, candidate, a, metrics)
        if best and any(best[1][k] != fallback[k] for k in keys):
            policies[name] = best[1]
            accepted[members] = best[2][members]
            audit[name] = {'before': original, 'after': best[3]}
    before = summarize(correct, old, known);after = summarize(correct, accepted, known)
    if after['wrong'] > before['wrong'] or after['negativeFalse'] > before['negativeFalse'] or after['correct'] < before['correct']:
        raise ValueError('Class gates exceeded the frozen global validation error budget')
    result = {**copy.deepcopy(baseline), 'classPolicies': policies, 'validation': after,
        'globalValidation': before, 'minimumCorrectClassSupport': minimum_support,
        'classPolicyScope': 'Predicted-class validation gates, sparse-class global fallback; not confidence probabilities.'}
    return result, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--negatives', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.archive.with_suffix('.json').read_text(encoding='utf-8'))
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    if evidence['split'] != 'val' or evidence['checkpointSha256'] != baseline['checkpointSha256'] or evidence['probabilitiesSha256'] != digest(args.archive):
        raise ValueError('Only checkpoint-bound validation archives can select gates')
    if baseline['testUsedForCalibration'] or baseline['watchClipsUsedForCalibration']:
        raise ValueError('Baseline calibration is not independent of Watch/test clips')
    a = np.load(args.archive, allow_pickle=False);n = np.load(args.negatives, allow_pickle=False)
    labels = list(a['labels'])
    if list(n['labels']) != labels or baseline['labels'] != labels:raise ValueError('Label order mismatch')
    from asl_model_tools import REPO
    manifest = json.loads((REPO / 'models/recognition-videos.json').read_text(encoding='utf-8'))
    watch = {s['originalFile'] for item in manifest['items'] for s in item.get('sources', [])}
    if any(Path(f).name in watch for f in list(a['files']) + list(n['files'])):raise ValueError('Watch clip in validation')
    p = np.concatenate([a['probabilities'], n['probabilities']])
    expected = np.concatenate([a['expected'], np.asarray(['__UNKNOWN__'] * len(n['expected']))])
    modes = {'full': labels} if baseline['family'] == 'beginner' else {'full': labels, 'core': CORE, 'extended': CORE + EXTRA}
    result = copy.deepcopy(baseline);result['classSelectionAudit'] = {}
    for mode, names in modes.items():
        result['policies'][mode], audit = fit_classes(p, expected, labels, names, baseline['policies'][mode])
        result['classSelectionAudit'][mode] = audit
        print(mode, len(audit), 'class policies', json.dumps(result['policies'][mode]['validation']), flush=True)
    result['sourceNegativeProbabilitiesSha256'] = digest(args.negatives)
    result['baselineCalibrationSha256'] = digest(args.baseline)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':main()
