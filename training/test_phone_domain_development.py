import unittest
from scripts.prepare_phone_domain_development import select

def source_map(overlap=False):
    return {split:dict(orig_name={str(i):f'4a.{person}-yes-2023_01_01_00_00_0{i}.000-0.mp4' for i,person in enumerate(ids)})
        for split,ids in [('train',['6001','6001','6002','6003']),('val',['6001' if overlap else '7001','7002','7003']),('test',['8031'])]}

class PhoneDomainTests(unittest.TestCase):
    def test_official_train_val_only_unique_signers_and_known_recording_exclusion(self):
        data=source_map();rows=select(data,'yes',set());self.assertEqual(len(rows),6)
        self.assertEqual({r['split'] for r in rows},{'train','val'});self.assertNotIn('8031',{r['participant'] for r in rows})
        excluded={tuple(rows[0]['recordingKey'])};other=select(data,'yes',excluded)
        self.assertNotIn(rows[0]['originalName'],[r['originalName'] for r in other])
    def test_signer_overlap_and_wrong_labels_rejected(self):
        with self.assertRaises(ValueError):select(source_map(True),'yes',set())
        with self.assertRaises(ValueError):select(source_map(),'no',set())

if __name__=='__main__':unittest.main()
