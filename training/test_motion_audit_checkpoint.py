import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.serve_motion_audit import CheckpointStore


class MotionAuditCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'audit'
        self.fixture = dict(items=[dict(id='hello', label='HELLO', video='media/hello.mp4', videoSha256='clip')])
        self.store = CheckpointStore(self.root, self.fixture)
        self.report = dict(schema=1, recognitionLabels=198, startedAt='run-1',
                           isolation=dict(host='127.0.0.1', realCameraCalls=0, microphoneCalls=0),
                           attempts=[dict(number=1, id='hello', label='HELLO', clip='media/hello.mp4',
                                          clipSha256='clip', rate=1, stage='baseline 1×', finishedAt='done',
                                          predicted=None, correct=False)])

    def tearDown(self):
        self.temp.cleanup()

    def test_checkpoint_preserves_miss_without_coordinates(self):
        self.assertEqual(self.store.save(self.report), 1)
        self.assertEqual(json.loads((self.root/'checkpoint.json').read_text(encoding='utf-8')), self.report)
        self.assertEqual(json.loads((self.root/'attempt-001.json').read_text(encoding='utf-8')), self.report['attempts'][0])
        self.assertEqual(self.store.save(copy.deepcopy(self.report)), 1)

    def test_completed_output_cannot_be_replaced(self):
        self.store.save(copy.deepcopy(self.report))
        self.report['attempts'][0].update(predicted='HELLO', correct=True)
        with self.assertRaisesRegex(ValueError, 'cannot be changed'):
            self.store.save(self.report)

    def test_unfinished_wrong_clip_duplicate_and_raw_data_rejected(self):
        for change in [dict(finishedAt=None), dict(clipSha256='wrong'), dict(rate=.5),
                       dict(correct=True), dict(landmarks=[]), dict(frames=[[1, 2, 3]])]:
            report = copy.deepcopy(self.report)
            report['attempts'][0].update(change)
            with self.assertRaises(ValueError):
                self.store.save(report)
        report = copy.deepcopy(self.report)
        report['attempts'] *= 2
        with self.assertRaises(ValueError):
            self.store.save(report)

    def test_another_run_or_physical_camera_cannot_overwrite(self):
        self.store.save(copy.deepcopy(self.report))
        self.report['startedAt'] = 'different'
        with self.assertRaises(ValueError):
            self.store.save(self.report)
        self.report['isolation']['realCameraCalls'] = 1
        with self.assertRaises(ValueError):
            self.store.save(self.report)

    def test_existing_run_directory_is_not_reused(self):
        with self.assertRaises(FileExistsError):
            CheckpointStore(self.root, self.fixture)


if __name__ == '__main__':
    unittest.main()
