import math,unittest
from scripts.train_manual_open_set_guard import apply_gate,select_gate,statistics


class ManualGuardSelectionTests(unittest.TestCase):
    def test_rejection_only_cannot_change_or_create_a_label(self):
        before=['A',None,'B'];stats=[(.2,.4,2),(.1,.2,2),(2,.2,.1)]
        self.assertEqual(apply_gate(before,stats,.5,1),['A',None,None])
    def test_selection_retains_each_correct_recording_and_reduces_negatives(self):
        rows=[{'label':x} for x in ['A','A','X','Y','A']];before=['A','A','A','A',None]
        stats=[(.1,.2,2),(.2,.4,2),(.8,.1,.125),(.9,.1,.111),(math.inf,math.inf,0)]
        p,c,out=select_gate(rows,before,stats,['A'],[.3,1],[0,1])
        self.assertTrue(p['enabled']);self.assertEqual(out,['A','A',None,None,None])
        self.assertEqual((c['after']['correct'],c['after']['negativeFalse']),(2,0))
    def test_improvement_that_drops_a_correct_accept_is_not_selected(self):
        rows=[{'label':'A'},{'label':'X'}];before=['A','A'];stats=[(1,.1,.1),(.1,1,10)]
        p,c,out=select_gate(rows,before,stats,['A'],[.2,2],[0,1])
        self.assertFalse(p['enabled']);self.assertEqual(out,before)
    def test_sparse_or_zero_negatives_does_not_manufacture_a_win(self):
        p,c,out=select_gate([{'label':'A'}],['A'],[(.1,.2,2)],['A'],[1],[0])
        self.assertFalse(p['enabled']);self.assertFalse(c['eligible'])
    def test_nonfinite_stats_fail_closed(self):
        self.assertEqual(apply_gate(['A'],[(math.inf,math.inf,0)],10,0),[None])
    def test_label_distance_competes_against_all_other_classes(self):
        import numpy as np
        s=statistics(np.array([.2,.4,.1]),[{'label':'A'},{'label':'A'},{'label':'X'}],'A')
        self.assertEqual(s[:2],(.2,.1));self.assertLess(s[2],1)


if __name__=='__main__':unittest.main()
