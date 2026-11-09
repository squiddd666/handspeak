import unittest
from scripts.prepare_browser_domain_development import select_sources


class DomainSelectionTests(unittest.TestCase):
    def test_prior_check_clips_and_outcomes_cannot_affect_selection(self):
        rows=[dict(file=f't{i}',split='train',participant='T',label='YES',prediction='WRONG',distance=100-i) for i in range(6)]
        rows+=[dict(file=f'v{i}',split='val',participant=f'V{i%2}',label='YES',prediction='YES',distance=i) for i in range(4)]
        chosen=select_sources(rows,{'t0','v0'},{'YES'})
        self.assertEqual([r['file'] for r in chosen],['t1','t2','t3','t4','v1','v2','v3'])
        for r in rows:r['prediction']='NO';r['distance']=0
        self.assertEqual([r['file'] for r in select_sources(rows,{'t0','v0'},{'YES'})],[r['file'] for r in chosen])
    def test_signer_leakage_is_rejected(self):
        rows=[dict(file='a',split='train',participant='SAME',label='YES'),dict(file='b',split='val',participant='SAME',label='YES')]
        with self.assertRaises(ValueError):select_sources(rows,set(),{'YES'})
    def test_sparse_support_is_not_fabricated(self):
        rows=[dict(file='a',split='train',participant='T',label='YES')]
        self.assertEqual(len(select_sources(rows,set(),{'YES'})),1)


if __name__=='__main__':unittest.main()
