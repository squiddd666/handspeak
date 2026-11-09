import unittest
from scripts.report_full198_browser import acceptable_labels,classify

class Full198AttributionTests(unittest.TestCase):
    def test_only_predeclared_dataset_aliases_are_matches(self):
        ref=dict(label='HOW',modelGlosses=['HOW1'])
        self.assertIn('HOW1',acceptable_labels(ref,'capstone'))
        self.assertNotIn('HOW2',acceptable_labels(ref,'capstone'))
        self.assertNotIn('HOW1',acceptable_labels(ref,'beginner'))
    def test_phrase_components_are_not_full_phrase_matches(self):
        ref=dict(label='GOOD MORNING',modelGlosses=['MORNING'])
        self.assertNotIn('MORNING',acceptable_labels(ref,'beginner'))
    def test_rejected_suggestions_remain_no_match(self):
        take=dict(label='YES',predicted=None,family='motion-manual',completeSourcePlayed=True,response=dict(rejectionReason='low-score',suggestions=[dict(label='YES')]))
        result=classify(take,dict(label='YES'));self.assertFalse(result['correct']);self.assertEqual(result['category'],'model-rejection:low-score')
    def test_wrong_accepts_and_capture_failures_are_not_hidden(self):
        r=classify(dict(label='YES',predicted='NO',family='motion-manual'),dict(label='YES'))
        self.assertEqual(r['category'],'accepted-wrong-word')
        r=classify(dict(label='YES',predicted=None,family='motion-manual',completeSourcePlayed=False),dict(label='YES'))
        self.assertEqual(r['category'],'source-playback-incomplete')

if __name__=='__main__':unittest.main()
