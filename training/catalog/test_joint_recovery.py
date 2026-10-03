import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import recover_joint_tracking as recovery


class RecoveryTests(unittest.TestCase):
    def test_selection_excludes_dense_usable_and_test_clips(self):
        row = dict(split='train', sequence=None, rawFrames=[[]]*30,
                   body=[None]*30, bodyMode='center-frame reference')
        self.assertEqual(recovery.select_clips([row]), [row])
        self.assertEqual(recovery.select_clips([dict(row, sequence=[[1]])]), [])
        self.assertEqual(recovery.select_clips([dict(row, rawFrames=[[]]*60)]), [])
        for bad in (dict(row, split='test'), dict(row, bodyMode='dynamic'),
                    dict(row, body=[None])):
            with self.assertRaises(ValueError):
                recovery.select_clips([bad])

    def test_recovery_preserves_source_and_realigns_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.mp4'
            source.write_bytes(b'placeholder recording')
            cache = root / 'cache'
            cache.mkdir()
            row = dict(file=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                       body=[{'pose': 1}]*2, rawFrames=[[], []])
            with patch.object(recovery.dense_extract, 'extract',
                              side_effect=lambda r: dict(r, rawFrames=[[], [], []], sequence=[[1]])):
                result = recovery.recover((row, cache))
                self.assertEqual(len(result['body']), 3)
                self.assertEqual(result['originalFile'], str(source))
                self.assertNotEqual(result['file'], str(source))
                self.assertEqual(len(row['body']), 2)
                self.assertEqual(source.read_bytes(), b'placeholder recording')
                with self.assertRaises(ValueError):
                    recovery.recover((dict(row, sha256='incorrect'), cache))


if __name__ == '__main__':
    unittest.main()
