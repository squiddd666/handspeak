import unittest
from scripts.train_manual_recovery import select_class_gate


class RecoverySelectionTests(unittest.TestCase):
    def test_sparse_and_single_signer_support_cannot_enable_recovery(self):
        s=[dict(label='YES',distance=.1,ratio=2.,votes=2)]*3
        self.assertIsNone(select_class_gate(s,['YES']*3,['P1']*3,'YES',[.2],[1.1],[2]))
        self.assertIsNone(select_class_gate(s[:2],['YES']*2,['P1','P2'],'YES',[.2],[1.1],[2]))
    def test_any_false_accept_disqualifies_the_gate(self):
        s=[dict(label='YES',distance=.1,ratio=2.,votes=2)]*4
        self.assertIsNone(select_class_gate(s,['YES']*3+['OTHER'],['P1','P2','P2','P3'],'YES',[.2],[1.1],[2]))
    def test_supported_correct_gate_returns_real_recording_indices(self):
        s=[dict(label='YES',distance=.1,ratio=2.,votes=2)]*3+[None]
        result=select_class_gate(s,['YES']*3+['NO'],['P1','P2','P2','P3'],'YES',[.2,.3],[1.1,1.5],[1,2])
        self.assertEqual(result[1],dict(maxDistance=.2,minRatio=1.5,minVotes=2));self.assertEqual(result[2],[0,1,2])


if __name__=='__main__':unittest.main()
