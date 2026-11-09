import unittest
from scripts.serve_full198_browser import payload_allowed


class FullAppTransportTests(unittest.TestCase):
    def test_original_payloads_are_preserved_but_target_hints_are_rejected(self):
        self.assertTrue(payload_allowed('/api/beginner-asl',dict(consent=True,frames=[])))
        self.assertTrue(payload_allowed('/api/capstone-asl',dict(consent=True,frames=[],vocabulary='core')))
        self.assertTrue(payload_allowed('/api/research-words',dict(consent=True,sequence=[])))
        self.assertFalse(payload_allowed('/api/beginner-asl',dict(consent=True,frames=[],label='YES')))
        self.assertFalse(payload_allowed('/api/capstone-asl',dict(consent=True,frames=[],vocabulary='core',minScore=0)))
        self.assertFalse(payload_allowed('/api/sessions',dict(consent=True,frames=[])))
        self.assertFalse(payload_allowed('/api/beginner-asl',dict(consent=False,frames=[])))


if __name__=='__main__':unittest.main()
