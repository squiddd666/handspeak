"""Source and validation-budget contracts for targeted dense retraining."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_native_repair_v4 import verify_splits,fitting_rows,merge_family,negatives,duplicates,body_row
from select_native_repair_v4 import eligible


def row(file,split='train',participant='P1',label='HELLO'):
    return dict(file=file,split=split,participant=participant,label=label,gloss=label,frames=[])


class NativeRepairTests(unittest.TestCase):
    def test_train_val_disjoint(self):
        verify_splits([row('a'),row('b','val','P2')],set())

    def test_source_leak_rejected(self):
        with self.assertRaisesRegex(ValueError,'source leakage'):
            verify_splits([row('a'),row('a','val','P2')],set())

    def test_signer_leak_rejected(self):
        with self.assertRaisesRegex(ValueError,'signer leakage'):
            verify_splits([row('a'),row('b','val','P1')],set())

    def test_watch_and_test_excluded(self):
        self.assertEqual([r['file'] for r in fitting_rows([row('a'),row('watch'),row('test','test','P3')],{'watch'})],['a'])
        with self.assertRaisesRegex(ValueError,'Watch'):
            verify_splits([row('watch')],{'watch'})
        with self.assertRaisesRegex(ValueError,'train/val'):
            verify_splits([row('test','test','P3')],set())

    def test_reextraction_not_extra_attempt(self):
        frame=dict(pose=[1],left=[1],right=None)
        native=dict(row('a'),beginnerLabel='HELLO',rawFrames=[1],frames=[frame])
        result,counts=merge_family([row('a')],[native],'beginnerLabel',['HELLO'])
        self.assertEqual(len(result),1);self.assertEqual(counts,dict(newSources=0,reextractedSources=1))
        self.assertEqual(result[0]['frames'],[frame]);self.assertNotIn('rawFrames',result[0])

    def test_runtime_body_capture_contract(self):
        frames=[dict(pose=[1],left=None,right=None),dict(pose=[1],left=[1],right=None)]
        result=body_row(dict(row('a'),frames=frames,bodyTimestamps=[0,1]),'HELLO')
        self.assertEqual(result['frames'],[frames[1]]);self.assertEqual(result['bodyTimestamps'],[1])
        self.assertIsNone(result['frames'][0]['right'])

    def test_known_alias_source_not_negative(self):
        known=[row('same',label='MY / MINE')]
        other=[row('same',label='MYMINE2'),row('negative',label='OTHER')]
        self.assertEqual([r['file'] for r in negatives(known,other,[],['MY / MINE'])],['negative'])

    def test_duplicate_hands_diagnostic_does_not_filter(self):
        hand=[[i/100,i/100,0] for i in range(21)]
        clip=dict(row('a'),frames=[dict(left=hand,right=hand)])
        d=duplicates([clip]);self.assertEqual(d['nearIdenticalXYFrames'],1)
        self.assertEqual(clip['frames'][0]['right'],hand)

    def test_no_error_tradeoff_promotion(self):
        before=dict(correct=10,wrong=2,negativeFalse=3)
        self.assertTrue(eligible(before,dict(correct=11,wrong=2,negativeFalse=3)))
        self.assertFalse(eligible(before,dict(correct=20,wrong=3,negativeFalse=3)))
        self.assertFalse(eligible(before,dict(correct=20,wrong=2,negativeFalse=4)))
        self.assertFalse(eligible(before,dict(correct=9,wrong=0,negativeFalse=0)))


if __name__=='__main__':unittest.main()
