import unittest
from scripts.train_browser_domain_recovery import select_guard, select_recovery

class BodyContextSelectionReuseTests(unittest.TestCase):
    def test_body_context_keeps_positive_retention_rules(self):
        rows=[dict(label='YES',participant=f'V{i}') for i in range(3)]+[dict(label='OTHER',participant='N')]
        stats=[dict(byLabel=dict(YES=.1,OTHER=1))]*3+[dict(byLabel=dict(YES=1,OTHER=.1))]
        gate=select_guard(rows,['YES']*4,stats,'YES',[.2],[1])
        self.assertEqual(gate[2],[0,1,2])
        self.assertIsNone(select_recovery(rows,['NO']*3+[None], [dict(label='YES',distance=.1,ratio=2,votes=2)]*4,'YES',[.2],[1.3],[2]))

if __name__=='__main__':unittest.main()
