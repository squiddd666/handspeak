import copy,json,tempfile,unittest
from pathlib import Path
from scripts.serve_dual_capture_audit import DualCaptureStore
class DualCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'audit'
        self.fixture=dict(fixtureSha256='frozen',items=[dict(id='no',label='NO',videoSha256='clip')])
        self.store=DualCaptureStore(self.root,self.fixture)
        self.report=dict(schema=2,fixtureSha256='frozen',realCameraCalls=0,microphoneCalls=0,startedAt='one',attempts=[
            dict(number=1,id='no',label='NO',clipSha256='clip',rate=1,status='complete',finishedAt='done',pairCount=1,processedFrames=1,
                 contractPassed=True,bodyOutputPreserved=True,sameEpoch=True,monotonicTimestamps=True,sameDimensions=True,pixelEquality=True,
                 samples=[dict(epoch=1,timestamp=1,width=640,height=480,pixelEquality=True)])])
    def tearDown(self):self.temp.cleanup()
    def test_scalar_pairs_are_saved_and_repeat_submission_is_idempotent(self):
        self.assertEqual(self.store.save(self.report),1);self.assertEqual(self.store.save(self.report),1)
        self.assertEqual(json.loads((self.root/'checkpoint.json').read_text()),self.report)
    def test_outcomes_cannot_be_replaced_or_relabelled(self):
        self.store.save(self.report)
        r=copy.deepcopy(self.report);r['attempts'][0]['status']='failed';r['attempts'][0]['contractPassed']=False
        with self.assertRaises(ValueError):self.store.save(r)
    def test_physical_camera_raw_landmarks_and_false_contracts_are_rejected(self):
        for change in [dict(landmarks=[]),dict(pairCount=2),dict(bodyOutputPreserved=False),dict(rate=.5)]:
            r=copy.deepcopy(self.report);r['attempts'][0].update(change)
            with self.assertRaises(ValueError):self.store.save(r)
        r=copy.deepcopy(self.report);r['realCameraCalls']=1
        with self.assertRaises(ValueError):self.store.save(r)
    def test_canceled_attempt_is_preserved_not_omitted(self):
        r=copy.deepcopy(self.report);r['attempts'][0].update(status='canceled',contractPassed=False,pairCount=0,samples=[])
        self.assertEqual(self.store.save(r),1)
    def test_duplicate_epochs_and_nonincreasing_times_cannot_claim_parity(self):
        r=copy.deepcopy(self.report);a=r['attempts'][0];a['pairCount']=a['processedFrames']=2;a['samples']*=2
        with self.assertRaises(ValueError):self.store.save(r)
    def test_unknown_image_payloads_and_disguised_coordinate_arrays_are_rejected(self):
        for where,key,value in [('attempt','image','encoded frame'),('attempt','error',[1,2,3]),('sample','pixels',[1,2,3])]:
            r=copy.deepcopy(self.report)
            target=r['attempts'][0] if where=='attempt' else r['attempts'][0]['samples'][0]
            target[key]=value
            with self.assertRaises(ValueError):self.store.save(r)
if __name__=='__main__':unittest.main()
