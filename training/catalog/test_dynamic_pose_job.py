import json
from pathlib import Path
import tempfile
import unittest
import run_dynamic_pose_training as job


class DynamicPoseJobTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'frames').mkdir();video=self.root/'video.mp4';video.write_bytes(b'fixture')
        self.row=dict(file=str(video),sha256=job.digest(video),label='HELLO',split='train',participant='training-signer')
        self.protocol=dict(implementationSha256=job.digest(job.__file__),encoders={})
        job.atomic_json(self.root/'extraction-protocol.json',self.protocol)
        self.sha=job.protocol_digest(self.protocol)
        self.cache=self.root/'frames'/(self.row['sha256']+'.json')
        self.record=dict(self.row,extractionProtocolSha256=self.sha,rawFrames=[[None,None]],body=[None],timestamps=[0])
        job.atomic_json(self.cache,self.record)
    def tearDown(self):
        self.temp.cleanup()
    def test_verified_cache_resumes_without_loading_detectors(self):
        self.assertEqual(job.extract((self.row,str(self.root),self.sha)),str(self.cache))
    def test_source_hash_change_is_rejected_even_with_cache(self):
        Path(self.row['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Recording differs'):
            job.extract((self.row,str(self.root),self.sha))
    def test_changed_cache_identity_and_alignment_are_rejected(self):
        for update, message in [(dict(split='val'),'identity'),(dict(body=[]),'aligned')]:
            job.atomic_json(self.cache,dict(self.record,**update))
            with self.assertRaisesRegex(ValueError,message):job.extract((self.row,str(self.root),self.sha))
    def test_changed_protocol_is_rejected_and_order_does_not_matter(self):
        self.assertEqual(job.protocol_digest(dict(a=1,b=2)),job.protocol_digest(dict(b=2,a=1)))
        job.atomic_json(self.root/'extraction-protocol.json',dict(self.protocol,changed=True))
        with self.assertRaisesRegex(ValueError,'protocol changed'):job.extract((self.row,str(self.root),self.sha))


if __name__=='__main__':unittest.main()
