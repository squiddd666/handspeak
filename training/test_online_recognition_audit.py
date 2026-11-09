import unittest,tempfile,json
from pathlib import Path
from scripts.report_online_recognition_audit import metrics
from scripts.serve_online_dual_audit import Store
from scripts.run_online_native_audit import FrozenManual,FrozenCandidate,ROOT

class OnlineRecognitionAuditTests(unittest.TestCase):
    def test_no_match_and_unsupported_acceptance_count_in_denominator(self):
        rows=[{'label':'HELLO'},{'label':'HELLO'},{'label':'HELLO'},{'label':'CAR'},{'label':'CAR'}]
        result=metrics(rows,['HELLO',None,'NO',None,'HELLO'],['HELLO','NO'])
        self.assertEqual(result,dict(positiveAttempts=3,matched=1,incorrect=1,noMatch=1,negativeAttempts=2,falseAccepts=1,correctRejections=1))
        with self.assertRaises(ValueError):metrics(rows,[],['HELLO'])
    def test_label_blind_manual_wrapper_matches_existing_js(self):
        manual=FrozenManual();base=manual.base;seq=base.refs[0];frames=[]
        for frame in seq:
            frames.append([[{'x':.5+frame[off+1+i*3]*.1,'y':.5+frame[off+2+i*3]*.1,'z':frame[off+3+i*3]*.1} for i in range(21)] if frame[off] else None for off in (0,64)])
        self.assertEqual(manual.predict(frames,1),base.predict(frames,1))
        self.assertEqual(manual.predict([[None,None]]*32,1),{m:None for m in ['default','expanded','daily','pack']})
    def test_candidate_rejects_missing_pose_hands_without_expected_label(self):
        candidate=FrozenCandidate(ROOT/'reports/motion-repair-v5-20261107/candidates/body-manual-24.json')
        self.assertFalse(candidate.predict([],1)['tracked']);self.assertIsNone(candidate.predict([],1)['prediction'])
    def test_scalar_store_rejects_replacing_past_outcomes_and_raw_arrays(self):
        cfg={'fixtureSha256':'frozen','items':[{'id':'first','label':'HELLO','videoSha256':'sha'}]}
        attempt=dict(number=1,id='first',label='HELLO',clipSha256='sha',startedAt='start',finishedAt='end',durationMs=4000,rate=1,
                     manualMode='all-four-frozen-modes',status='failed',pairCount=0,samples=[],contractPassed=False,
                     experimentalBodyPrediction=None,manualPredictions={m:None for m in ['default','expanded','daily','pack']})
        report=dict(schema=3,startedAt='start',fixtureSha256='frozen',scope='scalar-only',realCameraCalls=0,microphoneCalls=0,attempts=[attempt])
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'ledger',cfg);self.assertEqual(store.save(report),1)
            altered=json.loads(json.dumps(report));altered['attempts'][0]['status']='canceled'
            with self.assertRaises(ValueError):store.save(altered)
            altered=json.loads(json.dumps(report));altered['attempts'][0]['candidateDistance']=[[1,2,3]]
            with self.assertRaises(ValueError):store.save(altered)
            altered=json.loads(json.dumps(report));altered['attempts'][0]['manualPredictions']['expanded']='HELLO'
            with self.assertRaises(ValueError):store.save(altered)

if __name__=='__main__':unittest.main()
