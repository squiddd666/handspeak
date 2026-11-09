import unittest
from scripts.acquire_popsign_v2_missing_audit import safe_original

class ExactOriginalAcquisitionTests(unittest.TestCase):
    def test_exact_anonymous_original_name_only(self):
        name='baby/16f0-baby-2023_09_28_19_00_54.286-1.mp4'
        self.assertEqual(safe_original(name,'baby'),name.split('/')[1])
    def test_traversal_related_labels_and_previews_rejected(self):
        for name in ('../16f0-baby-2023_09_28_19_00_54.286-1.mp4','/baby/16f0-baby-2023_09_28_19_00_54.286-1.mp4',
            'baby/16f0-babysitter-2023_09_28_19_00_54.286-1.mp4','baby/preview.mp4','baby\\16f0-baby-2023_09_28_19_00_54.286-1.mp4'):
            with self.assertRaises(ValueError):safe_original(name,'baby')

if __name__=='__main__':unittest.main()
