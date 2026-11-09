import unittest
from scripts import prepare_phone_domain_feature_intake as mod

class PhoneFeatureIntakeTests(unittest.TestCase):
    def test_downloaded_train_val_rows_keep_identity_and_reject_overlap(self):
        downloads=[
            dict(status='downloaded',split='train',path=__file__,sha256='x',originalName='a.mp4',participant='6001',
                 label='YES',acquisitionId='phone-0001',publisherLabel='yes',recordingKey=['6001','yes-a']),
            dict(status='downloaded',split='val',path=__file__,sha256='x',originalName='b.mp4',participant='7001',
                 label='YES',acquisitionId='phone-0002',publisherLabel='yes',recordingKey=['7001','yes-b']),
            dict(status='download-failed',split='train',originalName='c.mp4'),
        ]
        original=mod.sha
        mod.sha=lambda path:'x'
        try:
            rows=mod.rows_from_acquisition(downloads)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['domain'],'phone-popsign-v1')
            self.assertEqual(mod.support_table(rows,['YES'])['YES']['train'],1)
            overlap=[dict(downloads[0]),dict(downloads[1],participant='6001')]
            with self.assertRaises(ValueError):
                mod.rows_from_acquisition(overlap)
        finally:
            mod.sha=original

if __name__=='__main__':unittest.main()
