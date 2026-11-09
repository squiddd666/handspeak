"""Frozen body-manual candidate compared with actual separate manual routes.

Only validation may select candidate-first vs fallback. Test never changes the
candidate or route policy. All negative signs and tracking misses are counted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

import numpy as np
import quickjs
from prepare_native_repair_v4 import REPO, read_rows, sources, verify_splits
from train_body_manual_v5 import prepare, matrix, gate_statistics, gate_mask
from train_native_manual_v4 import dtw_many, mirrored, metrics

BASELINE_FILES = {
    'base': 'models/asl-words.json', 'extra': 'models/asl-extra-words.json',
    'daily': 'models/research-words.json', 'pack': 'models/motion-categories/pack-dtw.json',
    'hello': 'models/hello-binary.json', 'baby': 'models/baby-binary.json', 'water': 'models/water-binary.json',
}
RUNTIME_FILES = ['gesture-model.js', 'motion-model.js', 'expanded-motion.js',
                 'temporal-motion/temporal-features.js', 'hello-binary.js']
MODES = {
    'default': ['HELLO', 'THANK YOU', 'PLEASE', 'YES', 'NO', 'FINISH', 'BABY'],
    'expanded': ['HELLO', 'THANK YOU', 'PLEASE', 'YES', 'NO', 'FINISH', 'BABY',
                 'DRINK', 'WATER', 'BOOK', 'FOOD', 'HUNGRY', 'LIKE', 'GO'],
    'daily': ['NAME', 'HOME', 'HAVE', 'WANT', 'LOVE'],
    'pack': ['FISH', 'PAIN', 'SEE', 'SICK', 'NIGHT'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Baseline:
    """Run real JS gating/ensemble code; cache the equivalent DTW primitive."""
    def __init__(self):
        self.js = quickjs.Context()
        for name in RUNTIME_FILES:
            code = (REPO/name).read_text(encoding='utf-8')
            self.js.eval(re.sub(r'^import .*?;\s*', '', code, flags=re.M).replace('export ', ''))
        models = {name: json.loads((REPO/path).read_text(encoding='utf-8')) for name, path in BASELINE_FILES.items()}
        self.js.eval('const auditModels = '+json.dumps(models)+';')
        self.js.eval('''
            const auditRefs = [], auditRefIds = new Map();
            function collectRefs(value) {
                if (!value || typeof value !== 'object') return;
                if (Array.isArray(value.samples)) for (const sample of value.samples) {
                    auditRefIds.set(sample.sequence, auditRefs.length);
                    auditRefs.push(sample.sequence);
                }
                for (const [key,child] of Object.entries(value)) if(key !== 'samples' && key !== 'weights') collectRefs(child);
            }
            collectRefs(auditModels);
            const auditRealDistance = motionDistance, auditRealMirror = mirrorMotion;
            let auditDirect, auditMirror;
            mirrorMotion = function(seq) { const out = auditRealMirror(seq); out.auditMirrored=true; return out; };
            motionDistance = function(a,b) {
                const index=auditRefIds.get(b);
                return index === undefined ? auditRealDistance(a,b) : (a.auditMirrored ? auditMirror : auditDirect)[index];
            };
            function prepareAudit(raw,aspect) {
                const frames=raw.map(f=>f.map(h=>isUsableHand(h)?h:null));
                return {frames,sequence:encodeMotion(frames,aspect)};
            }
            function baselineAudit(row,direct,mirror) {
                auditDirect=direct; auditMirror=mirror;
                const models=auditModels, seq=row.sequence, frames=row.frames, aspect=row.aspect;
                const specific=[models.hello,models.baby,models.water].map(m=>recognizeBinaryTemporal(m,frames,aspect));
                const motion = expanded => {
                    const positive=specific.filter((m,i)=>(expanded || i!==2) && m);
                    if(positive.length===1)return positive[0].label;
                    if(positive.length>1)return null;
                    return recognizeExpandedMotion(seq,models.base.samples,models.base.parameters,
                        expanded?models.extra:null,models.base.cameraCompatibility)?.label || null;
                };
                function dailyMatch(profile, allowed) {
                    const ranked=profile.samples.map(r=>({label:r.label,distance:Math.min(motionDistance(seq,r.sequence),motionDistance(mirrorMotion(seq),r.sequence))}));
                    // Python server sorts (distance,label), not JS insertion order.
                    ranked.sort((a,b)=>a.distance-b.distance || (a.label<b.label?-1:a.label>b.label?1:0));
                    const best=ranked[0],other=ranked.find(r=>r.label!==best.label),p=profile.parameters;
                    const ratio=(other?.distance ?? Infinity)/(best.distance+1e-6);
                    const votes=ranked.slice(0,3).filter(r=>r.label===best.label).length;
                    return allowed.includes(best.label) && best.distance<=(p.maxDistanceByLabel?.[best.label]??p.maxDistance)
                        && ratio>=p.minRatio && (votes>=p.minVotes || ratio>=(p.strongRatio??Infinity)) ? best.label : null;
                }
                let daily=null;
                if(validMotion(seq)) daily=dailyMatch(models.daily,models.daily.labels)
                    || dailyMatch(models.daily.cameraCompatibility,models.daily.cameraCompatibility.labels);
                const pack=recognizeMotion(seq,models.pack.samples,models.pack.parameters)?.label || null;
                return {default:motion(false), expanded:motion(true), daily,
                    pack:pack==='OTHER MOVEMENT'?null:pack};
            }
        ''')
        self.refs = np.asarray(json.loads(self.js.eval('JSON.stringify(auditRefs)')), float)

    def predict(self, raw, aspect):
        self.js.eval('var currentAudit=prepareAudit('+json.dumps(raw)+','+str(aspect)+'); currentAudit.aspect='+str(aspect)+';')
        seq = json.loads(self.js.eval('JSON.stringify(currentAudit.sequence)'))
        if seq is None:
            direct = mirror = np.full(len(self.refs), 1e100)
        else:
            a = np.asarray(seq)
            direct, mirror = dtw_many(a, self.refs), dtw_many(mirrored(a), self.refs)
        return json.loads(self.js.eval('JSON.stringify(baselineAudit(currentAudit,'+json.dumps(direct.tolist())+','+json.dumps(mirror.tolist())+'))'))


def combine(before, candidate, labels, policy):
    if policy == 'unchanged':
        return before
    if policy == 'candidate-first' and candidate is not None:
        return candidate if candidate in labels else None
    if policy == 'candidate-fallback' and before is not None:
        return before
    return (candidate if candidate in labels else None) if candidate is not None else before


def compare(rows, before, candidate, policies):
    result = {}
    for mode, labels in MODES.items():
        baseline = [p[mode] for p in before]
        after = [combine(b,c,labels,policies[mode]) for b,c in zip(baseline,candidate)]
        a,b = metrics(rows,baseline,labels), metrics(rows,after,labels)
        result[mode] = {'before':a,'after':b,'passed':b['correct']>=a['correct'] and b['wrong']<=a['wrong'] and b['negativeFalse']<=a['negativeFalse'],
                        'perLabel':{label:{'before':metrics([r for r in rows if r['label']==label],[p for r,p in zip(rows,baseline) if r['label']==label],labels),
                                           'after':metrics([r for r in rows if r['label']==label],[p for r,p in zip(rows,after) if r['label']==label],labels)} for label in labels}}
    return result


def audit(args):
    started = time.perf_counter()
    out = args.out
    if out.exists():
        raise FileExistsError(out)
    model = json.loads(args.model.read_text(encoding='utf-8'))
    validation = json.loads(args.model.with_suffix('.validation.json').read_text(encoding='utf-8'))
    if digest(args.model) != validation['modelSha256'] or validation['testUsedForSelection']:
        raise ValueError('Candidate is not frozen from validation')
    raw = read_rows(args.native)
    if len({r['file'] for r in raw}) != len(raw) or any(r.get('error') for r in raw):
        raise ValueError('Duplicate or failed extraction')
    expected_split = 'val' if args.stage=='validation' else 'test'
    raw = [r for r in raw if r['split']==expected_split]
    if args.stage=='test':
        selected = json.loads(args.selection.read_text(encoding='utf-8'))
        if {r['file'] for r in selected} != {r['file'] for r in raw}:
            raise ValueError('Incomplete held-out extraction')
    fit = read_rows(args.fitting)
    watch = {s['originalFile'] for item in json.loads((REPO/'models/recognition-videos.json').read_text(encoding='utf-8'))['items'] for s in item.get('sources',[])}
    verify_splits(fit, watch)
    if args.stage=='test':
        fitted_sources = set().union(*(sources(r) for r in fit))
        fitted_signers = {r['participant'] for r in fit}
        if any(sources(r)&(fitted_sources|watch) or r['participant'] in fitted_signers for r in raw):
            raise ValueError('Held-out source/signer/Watch leakage')
    rows = prepare(raw)
    refs = model['samples']
    d = matrix(rows,refs,model['featureParameters'])
    stats = gate_statistics(d,refs,model['labels'])
    candidate = [str(label) if accepted else None for label,accepted in zip(stats[0],gate_mask(stats,model['parameters']))]
    baseline = Baseline()
    before = []
    for i,row in enumerate(raw):
        before.append(baseline.predict(row['rawFrames'],row['imageAspect']))
        if (i+1)%20==0: print('Baseline',i+1,'/',len(raw),flush=True)
    hashes = {path:digest(REPO/path) for path in list(BASELINE_FILES.values())+RUNTIME_FILES}
    if args.stage=='validation':
        policies = {}
        for mode in MODES:
            best = None
            for policy in ['candidate-fallback','candidate-first']:
                p = {m:policy for m in MODES}
                c = compare(rows,before,candidate,p)[mode]
                if not c['passed']: continue
                a = c['after']; key=(a['correct'],-a['wrong'],-a['negativeFalse'])
                if best is None or key>best[0]: best=(key,policy)
            policies[mode] = best[1] if best else 'unchanged'
    else:
        frozen = json.loads(args.route_policy.read_text(encoding='utf-8'))
        if frozen['modelSha256']!=digest(args.model) or frozen['baselineSha256']!=hashes:
            raise ValueError('Candidate/baseline changed since route selection')
        policies = frozen['routePolicies']
    # Unchanged is an explicit no-promotion route, not a new acceptance gate.
    comparison = compare(rows,before,candidate,policies)
    eligible = [mode for mode,p in policies.items() if p!='unchanged' and comparison[mode]['passed']
                and comparison[mode]['after']['correct']>comparison[mode]['before']['correct']]
    result = dict(stage=args.stage, split=expected_split,modelSha256=digest(args.model),baselineSha256=hashes,
                  nativeSha256=digest(args.native),routePolicies=policies,comparison=comparison,eligibleModes=eligible,
                  candidate=metrics(rows,candidate,model['labels']),testUsedForSelection=False,
                  watchExcluded=True,sourcesAndParticipantsDisjoint=True,deployed=False,
                  records=[dict(file=r['file'],expected=r['label'],candidate=c,baseline=b,trackedFrames=r['trackedFrames']) for r,c,b in zip(rows,candidate,before)],
                  seconds=round(time.perf_counter()-started,2),
                  scope='Paired recorded regression. Native whole-clip sampling, not a live-camera accuracy claim. Body capture and Tasks hand capture are distinct actual tracker outputs from the same source timestamps.')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({m:{k:v for k,v in c.items() if k!='perLabel'} for m,c in comparison.items()},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['validation','test'],required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--fitting',type=Path,required=True)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--route-policy',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    audit(parser.parse_args())
