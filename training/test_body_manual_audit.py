import sys
import unittest
from pathlib import Path
import json

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_body_manual_v5 import Baseline, combine
from body_manual_features import dtw_many


class BodyManualAuditTests(unittest.TestCase):
    def test_routes_do_not_add_words_to_public_vocabulary(self):
        labels=['HELLO','PLEASE']
        self.assertIsNone(combine('HELLO','DRINK',labels,'candidate-first'))
        self.assertEqual(combine('HELLO','DRINK',labels,'candidate-fallback'),'HELLO')
        self.assertIsNone(combine(None,'DRINK',labels,'candidate-fallback'))
        self.assertEqual(combine('HELLO','PLEASE',labels,'unchanged'),'HELLO')

    def test_vectorized_cost_matches_explicit_original(self):
        rng=np.random.default_rng(17)
        a=rng.normal(size=(20,146));refs=rng.normal(size=(3,20,146))
        a[:,-2:]=rng.integers(0,2,(20,2));refs[:,:,-2:]=rng.integers(0,2,(3,20,2))
        cost=.15*np.sqrt(np.mean((a[None,:,None,:14]-refs[:,None,:,:14])**2,axis=-1))
        for side in range(2):
            both=a[None,:,None,144+side]*refs[:,None,:,144+side]
            missing=a[None,:,None,144+side]!=refs[:,None,:,144+side]
            wrist=slice(14+side*2,16+side*2);shape=slice(18+side*63,81+side*63)
            w=np.sqrt(np.mean((a[None,:,None,wrist]-refs[:,None,:,wrist])**2,axis=-1))
            delta=a[None,:,None,shape]-refs[:,None,:,shape];delta[...,2::3]*=.5
            cost+=(w+.5*np.sqrt(np.mean(delta**2,axis=-1)))*both+.75*missing
        expected=[]
        for c in cost:
            dp=np.full((21,21),np.inf);dp[0,0]=0
            for i in range(1,21):
                for j in range(max(1,i-5),min(20,i+5)+1):
                    dp[i,j]=c[i-1,j-1]+min(dp[i-1,j],dp[i,j-1],dp[i-1,j-1])
            expected.append(dp[20,20]/20)
        np.testing.assert_allclose(dtw_many(a,refs),expected,rtol=1e-12,atol=1e-12)

    def test_baseline_distance_cache_matches_actual_js(self):
        baseline=Baseline()
        # A frozen existing template re-expressed as actual raw points, not an
        # expected output substituted into the classifier.
        seq=baseline.refs[0]
        frames=[]
        for frame in seq:
            hands=[]
            for off in (0,64):
                hands.append([{'x':.5+frame[off+1+i*3]*.1,'y':.5+frame[off+2+i*3]*.1,'z':frame[off+3+i*3]*.1} for i in range(21)] if frame[off] else None)
            frames.append(hands)
        cached=baseline.predict(frames,1)
        baseline.js.eval('motionDistance=auditRealDistance;')
        actual=json.loads(baseline.js.eval('JSON.stringify(baselineAudit(currentAudit,auditDirect,auditMirror))'))
        self.assertEqual(cached,actual)


if __name__=='__main__': unittest.main()
