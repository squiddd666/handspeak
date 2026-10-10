"""Exercise failure/continuation boundaries without launching training or deployment."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_single_word_queue as queue


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.patches = [patch.object(queue, 'REPORT', root/'reports'), patch.object(queue, 'BASE', root/'private'),
                        patch.object(queue, 'WORDS', ['FIND', 'FISH']),
                        patch.object(queue.subprocess, 'run', return_value=type('Result', (), {'returncode': 3})())]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)

    def complete(self, word, passes):
        directory = queue.REPORT / word.lower(); directory.mkdir(parents=True, exist_ok=True)
        (directory/'completion.json').write_text(json.dumps({'passesDevelopmentScreen': passes}))

    def status(self):
        return json.loads((queue.REPORT/'queue-status.json').read_text())

    def test_failed_development_advances_without_testing_or_publishing(self):
        self.complete('FIND', False); self.complete('FISH', False)
        with patch.object(queue, 'run') as run:
            queue.main(); run.assert_not_called()
        self.assertEqual(self.status()['state'], 'complete')
        self.assertEqual(len(self.status()['completed']), 2)
        self.assertFalse(self.status()['deployed'])

    def test_sign_gate_pass_publishes_under_owner_waiver_then_continues(self):
        self.complete('FIND', True)
        self.complete('FISH', False)
        (queue.REPORT/'find/release-status.json').write_text(json.dumps(
            {'stage': 'recording-check-complete', 'state': 'complete', 'passesFreshSignGate': True}))
        with patch.object(queue, 'run') as run:
            queue.main(); run.assert_called_once_with('publish_single_word.py', 'FIND')
        self.assertEqual(self.status()['state'], 'complete')
        self.assertTrue(self.status()['deployed'])

    def test_interrupted_training_is_not_overwritten(self):
        directory = queue.BASE/'find'; directory.mkdir(parents=True)
        (directory/'plan.json').write_text('{}')
        with patch.object(queue, 'run') as run, self.assertRaisesRegex(RuntimeError, 'Interrupted frozen'):
            queue.main()
        run.assert_not_called(); self.assertEqual(self.status()['state'], 'failed')

    def test_operational_failure_stops_instead_of_claiming_model_failure(self):
        self.complete('FIND', True)
        with patch.object(queue, 'run', side_effect=RuntimeError('download unavailable')), self.assertRaises(RuntimeError):
            queue.main()
        self.assertEqual(self.status()['state'], 'failed')
        self.assertEqual(self.status()['completed'], [])


if __name__ == '__main__':
    unittest.main()
