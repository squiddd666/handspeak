import unittest
from scripts.train_browser_domain_recovery import select_guard,select_recovery

class DomainTrainingSelectionTests(unittest.TestCase):
    def test_guard_requires_its_own_correct_class_signer_support(self):
        rows=[dict(label='YES',participant='V1')]*3;before=['YES']*3
        stats=[dict(byLabel=dict(YES=.1,OTHER=1))]*3
        self.assertIsNone(select_guard(rows,before,stats,'YES',[.2],[1]))
        rows[2]=dict(label='YES',participant='V2')
        # No wrong accept to fix: no needless guard deployment.
        self.assertIsNone(select_guard(rows,before,stats,'YES',[.2],[1]))
    def test_guard_must_retain_every_correct_recording(self):
        rows=[dict(label='YES',participant=f'V{i}') for i in range(3)]+[dict(label='OTHER',participant='N')]
        stats=[dict(byLabel=dict(YES=.1,OTHER=1))]*3+[dict(byLabel=dict(YES=1,OTHER=.1))]
        gate=select_guard(rows,['YES']*4,stats,'YES',[.2],[1])
        self.assertEqual(gate[2],[0,1,2]);self.assertIsNone(select_guard(rows,['YES']*4,stats,'YES',[.01],[1]))
    def test_recovery_needs_three_correct_recordings_two_signers_zero_false_accepts(self):
        rows=[dict(label='YES',participant=f'V{i}') for i in range(3)]
        stats=[dict(label='YES',distance=.1,ratio=2,votes=2)]*3
        chosen=select_recovery(rows,[None]*3,stats,'YES',[.2],[1.3],[2]);self.assertEqual(chosen[2],[0,1,2])
        rows.append(dict(label='OTHER',participant='N'));stats.append(stats[0])
        self.assertIsNone(select_recovery(rows,[None]*4,stats,'YES',[.2],[1.3],[2]))
    def test_recovery_never_replaces_an_existing_accept(self):
        rows=[dict(label='YES',participant=f'V{i}') for i in range(3)]
        stats=[dict(label='YES',distance=.1,ratio=2,votes=2)]*3
        self.assertIsNone(select_recovery(rows,['NO']*3,stats,'YES',[.2],[1.3],[2]))

if __name__=='__main__':unittest.main()
