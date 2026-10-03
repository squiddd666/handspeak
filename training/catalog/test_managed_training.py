import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_balanced_training as runner


class ManagedTrainingTests(unittest.TestCase):
    def test_stage_failure_stops_before_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runner, 'ROOT', root), patch.object(runner.subprocess, 'run',
                    return_value=SimpleNamespace(returncode=7)) as command:
                with self.assertRaises(SystemExit) as error:
                    runner.main()
                self.assertEqual(error.exception.code, 7)
                self.assertEqual(command.call_count, 1)
                status = json.loads((root / 'job-status.json').read_text())
                self.assertEqual(status['stage'], 'download')
                self.assertEqual(status['state'], 'failed')
                self.assertFalse(status['deployed'])

    def test_validation_pass_does_not_claim_independent_accuracy_or_deploy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'reports'
            report.mkdir()
            (report / 'validation.json').write_text(json.dumps({'selected': {
                'passesValidation': True, 'validation': {'correct': 120}}}))
            for name in ('expansion-protocol.json', 'extraction-protocol.json', 'coverage.json'):
                (root / name).write_text('{}')
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'REPORT', report), \
                    patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as command:
                runner.main()
                self.assertEqual(command.call_count, 5)
                status = json.loads((root / 'job-status.json').read_text())
                self.assertTrue(status['passesValidation'])
                self.assertFalse(status['independentAccuracyPassed'])
                self.assertFalse(status['deployed'])
                self.assertEqual(status['state'], 'complete')


if __name__ == '__main__':
    unittest.main()
