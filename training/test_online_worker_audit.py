import copy, tempfile, threading, unittest
from pathlib import Path
from scripts.serve_online_worker_audit import Store, MODES, compact_result
from scripts.report_online_worker_audit import score


class WorkerAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.receipts={}
        self.cfg=dict(fixtureSha256='frozen',items=[dict(id='one',label='HELLO',videoSha256='clip')])
        self.store=Store(Path(self.temp.name)/'ledger',self.cfg,self.receipts)
        self.skipped=dict(accepted=None,rejectionReason='capture-unusable',error=None,httpStatus=None,checkpointSha256=None,auxiliarySha256=None)
        a=dict(number=1,id='one',label='HELLO',clipSha256='clip',startedAt='start',durationMs=4000,rate=1,sourceDuration=3,
            manualMode='all-four-frozen-modes',status='complete',error=None,finishedAt='end',pairCount=1,bodyFrames=1,
            bodyOutputPreserved=True,manualFrames=1,manualTrackedFrames=1,sameEpoch=True,monotonicTimestamps=True,
            sameDimensions=True,pixelEquality=True,sampledFrames=1,processedFrames=1,tracker='dual',contractPassed=True,
            samples=[dict(epoch=1,timestamp=1,width=640,height=480,pixelEquality=True,bodyHands=1,manualHands=1,bodyPose=True)],
            experimentalBodyPrediction=None,manualPredictions=dict(default=None,expanded=None,daily=None,pack=None),
            candidateTracked=False,candidateDistance=None,candidateSeparation=None,candidateVotes=0,playbackTruncated=False,
            trackerExecutionContext='worker',bodyTracker='Worker Holistic',manualEncodingUsable=False,productionPredictions={m:dict(self.skipped) for m in MODES})
        self.report=dict(schema=4,startedAt='start',fixtureSha256='frozen',scope='audit',realCameraCalls=0,microphoneCalls=0,attempts=[a])
    def tearDown(self): self.temp.cleanup()
    def test_append_only_and_idempotent(self):
        self.assertEqual(self.store.save(self.report),1); self.assertEqual(self.store.save(self.report),1)
        r=copy.deepcopy(self.report); r['attempts'][0]['error']='replace'
        with self.assertRaises(ValueError):self.store.save(r)
    def test_raw_fields_and_main_thread_contract_rejected(self):
        for key,value in [('landmarks',[]),('error',[1,2]),('trackerExecutionContext','main-thread'),('bodyFrames',2)]:
            r=copy.deepcopy(self.report);r['attempts'][0][key]=value
            with self.assertRaises(ValueError):self.store.save(r)
    def test_five_frame_minimum_and_real_receipts(self):
        r=copy.deepcopy(self.report);a=r['attempts'][0]
        a.update(pairCount=5,bodyFrames=5,manualFrames=5,manualTrackedFrames=5,processedFrames=5)
        a['samples']=[dict(a['samples'][0],timestamp=i+1) for i in range(5)]
        result=dict(accepted='HELLO',rejectionReason=None,error=None,httpStatus=200,checkpointSha256='base',auxiliarySha256=None)
        for mode in MODES:
            self.receipts[('one',mode)]={'result':dict(result)};a['productionPredictions'][mode]=dict(result)
        self.assertEqual(self.store.save(r),1)
    def test_unusable_cannot_accept_api_prediction(self):
        r=copy.deepcopy(self.report);r['attempts'][0]['productionPredictions']['beginner']['accepted']='HELLO'
        with self.assertRaises(ValueError):self.store.save(r)
    def test_failed_capture_cannot_accept_manual(self):
        r=copy.deepcopy(self.report);a=r['attempts'][0];a.update(status='failed',contractPassed=False);a['manualPredictions']['default']='HELLO'
        with self.assertRaises(ValueError):self.store.save(r)
    def test_unaccepted_suggestions_never_matches(self):
        result=compact_result(dict(predictions=[],suggestions=[dict(label='HELLO')],rejectionReason='ambiguous'),200)
        self.assertIsNone(result['accepted'])
    def test_exact_labels_and_negative_denominator(self):
        rows=[dict(label='FOOD',prediction='EAT1'),dict(label='EAT1',prediction=None),dict(label='EAT1',prediction='EAT1')]
        s=score(rows,['EAT1']);self.assertEqual((s['positives'],s['matched'],s['noMatch'],s['negativeFalseAcceptances']),(2,1,1,1))
    def test_no_positive_accuracy_is_not_zero_accuracy(self):
        self.assertIsNone(score([dict(label='FOOD',prediction=None)],['EAT1'])['positiveRecall'])
    def test_failure_is_in_positive_denominator(self):
        s=score([dict(label='HELLO',prediction=None)],['HELLO']);self.assertEqual((s['positives'],s['noMatch']),(1,1))
    def test_physical_camera_rejected(self):
        r=copy.deepcopy(self.report);r['realCameraCalls']=1
        with self.assertRaises(ValueError):self.store.save(r)


if __name__=='__main__':unittest.main()
