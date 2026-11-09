import copy,json,tempfile,unittest
from pathlib import Path
from scripts.serve_browser_domain_capture import FeatureStore,validate
from scripts.freeze_browser_domain_capture import render

def outcome():
    sample=dict(epoch=1,timestamp=1100,width=640,height=480,pixelEquality=True,
        usedHandFallback=False,body=dict(pose=[[.1,.2,0]]*7,left=[[.1,.2,0]]*21,right=None),
        manual=[None,[dict(x=.1,y=.2,z=0)]*21])
    checks={k:True for k in ('bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality',
        'pairedProcessing','productionSampling','recordingGeometry','workerExecution')}
    return dict(number=1,id='domain-001',sourceSha256='abc',startedAt='start',finishedAt='end',status='complete',error=None,
        rate=1,durationMs=4000,sourceDuration=2.,playbackTruncated=False,start=1000,deadline=5000,
        sampledFrames=1,processedFrames=1,warmupFrames=1,poseWarmupFrames=1,trackerExecutionContext='worker',tracker='dual',
        bodyTracker='Holistic',realCameraCalls=0,microphoneCalls=0,checks=checks,contractPassed=True,samples=[sample])
REF=dict(id='domain-001',videoSha256='abc')

class DomainCaptureTests(unittest.TestCase):
    def test_only_valid_measured_stream_is_eligible(self):
        self.assertEqual(validate(outcome(),REF,1),dict(pairCount=1,bodyFrames=1,manualTrackedFrames=1))
    def test_images_labels_predictions_and_nonfinite_values_rejected(self):
        for key in ('image','prediction','expectedWord','label'):
            r=outcome();r[key]='forbidden'
            with self.assertRaises(ValueError):validate(r,REF,1)
        for value in (float('nan'),float('inf'),1000):
            r=outcome();r['samples'][0]['manual'][1][0]['x']=value
            with self.assertRaises(ValueError):validate(r,REF,1)
    def test_frozen_identity_order_and_camera_prohibitions(self):
        for key,value in (('id','other'),('sourceSha256','changed'),('number',2),('realCameraCalls',1),('microphoneCalls',1),('rate',.5)):
            r=outcome();r[key]=value
            with self.assertRaises(ValueError):validate(r,REF,1)
    def test_contract_claims_are_checked_against_pairs(self):
        for mutate in (lambda r:r.update(processedFrames=2),lambda r:r['samples'][0].update(width=960),
            lambda r:r['samples'][0].update(pixelEquality=False),lambda r:r.update(poseWarmupFrames=0),
            lambda r:r.update(deadline=6000),lambda r:r['samples'][0].update(timestamp=999)):
            r=outcome();mutate(r)
            with self.assertRaises(ValueError):validate(r,REF,1)
    def test_failure_is_preserved_and_not_eligible_for_fitting(self):
        r=outcome();r.update(status='failed',error='timeout',contractPassed=False)
        self.assertEqual(validate(r,REF,1)['pairCount'],1)
        with tempfile.TemporaryDirectory() as tmp:
            source=dict(split='train',file='a.mp4',participant='T',label='YES')
            store=FeatureStore(Path(tmp)/'features',dict(items=[REF]),[source]);store.save(r)
            feature=json.loads((Path(tmp)/'features/feature-001.json').read_text('utf-8'))
            self.assertFalse(feature['trainingAllowed']);self.assertFalse(feature['calibrationAllowed'])
            self.assertEqual(len(feature['capture']['samples']),1)
    def test_empty_failed_warmup_counts_match_transmitted_zero_metrics(self):
        r=outcome();r.update(status='failed',error='warmup failed',contractPassed=False,start=None,deadline=None,
            sampledFrames=0,processedFrames=0,warmupFrames=0,poseWarmupFrames=0,trackerExecutionContext=None,samples=[])
        r['checks']={k:k in ('bodyOutputPreserved','pairedProcessing','monotonicTimestamps') for k in r['checks']}
        self.assertEqual(validate(r,REF,1),dict(pairCount=0,bodyFrames=0,manualTrackedFrames=0))
    def test_store_is_append_only_and_split_permissions_cannot_be_changed(self):
        for split in ('train','val'):
            with tempfile.TemporaryDirectory() as tmp:
                source=dict(split=split,file='a.mp4',participant='T',label='YES')
                store=FeatureStore(Path(tmp)/'features',dict(items=[REF]),[source]);receipt=store.save(outcome())
                p=Path(tmp)/'features/feature-001.json';before=p.read_bytes();self.assertEqual(receipt['saved'],1)
                with self.assertRaises(ValueError):store.save(outcome())
                self.assertEqual(p.read_bytes(),before)
                saved=json.loads(before);self.assertEqual(saved['trainingAllowed'],split=='train');self.assertEqual(saved['calibrationAllowed'],split=='val')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):FeatureStore(Path(tmp)/'features',dict(items=[REF]),[dict(split='test')])
    def test_html_does_not_rewrite_allowlist_or_embed_labels(self):
        cfg=dict(items=[REF],allowedFiles={'/training/experimental/domain_capture_contract.mjs':'exact/path'},token='token')
        html=render(cfg);encoded=html.split('window.DOMAIN_CAPTURE_FIXTURE = ',1)[1].split(';</script>',1)[0]
        self.assertEqual(json.loads(encoded),cfg);self.assertNotIn('expectedWord',html)

if __name__=='__main__':unittest.main()
