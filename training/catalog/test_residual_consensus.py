import unittest
import numpy as np
from check_residual_consensus import guarded_outputs, batch


class ConsensusTest(unittest.TestCase):
    def setUp(self):
        self.old=batch.trainer.LABELS;batch.trainer.LABELS=['ONE','TWO']
    def tearDown(self):
        batch.trainer.LABELS=self.old
    def test_guard_is_veto_only_not_a_second_predictor(self):
        rows=[dict(sequence=[1])]
        members=np.array([[[.95,.03,.02]]]*3)
        rejection=np.array([[.1,.1,.8]])
        self.assertEqual(guarded_outputs(rows,members,rejection,.5,0,2,True),[None])
        self.assertEqual(guarded_outputs(rows,members,rejection,.5,0,2,False),['ONE'])
        supported=np.array([[.1,.8,.1]])
        self.assertEqual(guarded_outputs(rows,members,supported,.5,0,2,True),['ONE'])
    def test_agreement_never_overrides_sequence_quality_or_negative_winner(self):
        rows=[dict(sequence=None),dict(sequence=[1])]
        members=np.array([[[.95,.03,.02],[.1,.1,.8]]]*3)
        self.assertEqual(guarded_outputs(rows,members,members[0],.35,0,3,False),[None,None])
    def test_required_votes_reject_disagreement(self):
        rows=[dict(sequence=[1])]
        members=np.array([[[.9,.05,.05]],[[.9,.05,.05]],[[.1,.85,.05]]])
        guard=np.array([[.8,.1,.1]])
        self.assertEqual(guarded_outputs(rows,members,guard,.35,0,2,True),['ONE'])
        self.assertEqual(guarded_outputs(rows,members,guard,.35,0,3,True),[None])


if __name__=='__main__':unittest.main()
