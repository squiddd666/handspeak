import unittest
from scripts.inventory_full_recognition_support import support,choose,PHRASES

class FullSupportTests(unittest.TestCase):
    def test_exact_glosses_exclusions_and_uncached_counts(self):
        rows=[dict(file='a',split='train',gloss='LOVE',participant='T'),dict(file='b',split='train',gloss='LOVE',participant='T2'),
            dict(file='c',split='val',gloss='LOVE',participant='V'),dict(file='d',split='val',gloss='LOVELY',participant='V2')]
        result=support({'LOVE'},rows,{'a'},{'b':'b.mp4'})
        self.assertEqual(result['train']['originalRecordings'],1);self.assertEqual(result['train']['cachedOriginals'],1)
        self.assertEqual(result['val']['originalRecordings'],1);self.assertEqual(result['val']['cachedOriginals'],0)
    def test_signer_diversity_uses_metadata_not_prediction_quality(self):
        rows=[dict(file='a',participant='T',prediction='YES'),dict(file='b',participant='T',prediction='YES'),
            dict(file='c',participant='T2',prediction=None),dict(file='d',participant='T3',prediction='NO')]
        self.assertEqual([r['file'] for r in choose(rows,3)],['a','c','d'])
        for r in rows:r['prediction']='WRONG'
        self.assertEqual([r['file'] for r in choose(rows,3)],['a','c','d'])
    def test_phrase_components_are_never_natural_phrase_support(self):
        self.assertIn('GOOD MORNING',PHRASES);self.assertNotIn('MORNING',PHRASES)

if __name__=='__main__':unittest.main()
