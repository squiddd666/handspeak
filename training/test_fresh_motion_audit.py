import copy,tempfile,unittest
from pathlib import Path
from scripts.prepare_fresh_motion_audit import validate_intake,sha
class FreshAuditIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'hello.mp4').write_bytes(b'new clip 1');(self.root/'other.mp4').write_bytes(b'new clip 2')
        self.manifest=dict(purpose='audit-only',consentConfirmed=True,newSignerDeclaration=True,clips=[
            dict(path='hello.mp4',label='HELLO',signerId='NEW01',sourceId='new1',negative=False),
            dict(path='other.mp4',label='CAR',signerId='NEW02',sourceId='new2',negative=True)])
    def tearDown(self):self.temp.cleanup()
    def validate(self,manifest=None,signers=set(),files=set(),hashes=set()):
        return validate_intake(manifest or self.manifest,self.root,signers,files,hashes)
    def test_intake_keeps_unknown_signs_and_does_not_copy_or_modify_videos(self):
        before=copy.deepcopy(self.manifest);records=self.validate()
        self.assertEqual(len(records),2);self.assertTrue(records[1]['negative']);self.assertEqual(records[1]['split'],'test')
        self.assertEqual(self.manifest,before);self.assertEqual((self.root/'hello.mp4').read_bytes(),b'new clip 1')
        self.assertEqual(len(list(self.root.iterdir())),2)
    def test_consent_new_signer_and_audit_only_purpose_are_explicit(self):
        for key,value in [('consentConfirmed',False),('newSignerDeclaration',False),('purpose','train')]:
            m=copy.deepcopy(self.manifest);m[key]=value
            with self.assertRaises(ValueError):self.validate(m)
    def test_used_signer_source_and_content_are_rejected(self):
        for kwargs in [dict(signers={'NEW01'}),dict(files={'new1'}),dict(hashes={sha(self.root/'hello.mp4')})]:
            with self.assertRaises(ValueError):self.validate(**kwargs)
    def test_duplicates_and_wrong_negative_flag_are_rejected(self):
        for change in [dict(path='hello.mp4'),dict(sourceId='new1'),dict(label='HELLO'),dict(negative='true')]:
            m=copy.deepcopy(self.manifest);m['clips'][1].update(change)
            with self.assertRaises(ValueError):self.validate(m)
    def test_missing_recordings_do_not_create_a_fresh_audit(self):
        m=copy.deepcopy(self.manifest);m['clips']=[]
        with self.assertRaises(ValueError):self.validate(m)
    def test_whitespace_and_case_cannot_hide_a_used_signer_or_source(self):
        m=copy.deepcopy(self.manifest);m['clips'][0]['signerId']=' new01 '
        with self.assertRaises(ValueError):self.validate(m,signers={'NEW01'})
        m=copy.deepcopy(self.manifest);m['clips'][0]['sourceId']=' NEW1 '
        with self.assertRaises(ValueError):self.validate(m,files={'new1'})
        with self.assertRaises(ValueError):self.validate(files={'HELLO.MP4'})
if __name__=='__main__':unittest.main()
