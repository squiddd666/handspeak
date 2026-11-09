import unittest
from scripts.prepare_full_family_body_domain_development import gloss_to_label

class FullFamilyBodyDomainTests(unittest.TestCase):
    def test_manual_and_beginner_gloss_labels_are_exact(self):
        beginner={'FOOD':['EAT1'],'MORNING':['MORNING']}
        self.assertEqual(gloss_to_label('THANKYOU',beginner),'THANK YOU')
        self.assertEqual(gloss_to_label('EAT1',beginner),'FOOD')
        self.assertEqual(gloss_to_label('MORNING',beginner),'MORNING')
        self.assertEqual(gloss_to_label('AFTER',beginner),'AFTER')

if __name__=='__main__':unittest.main()
