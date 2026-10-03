import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import test_frozen_expansion as experiment


class FreshProtocolTests(unittest.TestCase):
    def test_masked_winner_is_rejected_without_fallback(self):
        probabilities = np.zeros((4, 11))
        probabilities[0, experiment.batch.LABELS.index('MILK')] = .98
        probabilities[0, experiment.batch.LABELS.index('READ')] = .02
        probabilities[1, experiment.batch.LABELS.index('GIVE')] = .99
        probabilities[2, experiment.batch.LABELS.index('READ')] = .99
        probabilities[3, experiment.batch.LABELS.index('READ')] = .99
        rows = [{'sequence': [[1]]}] * 3 + [{'sequence': None}]
        self.assertEqual(experiment.predict(rows, probabilities, .97, 0),
                         [None, None, 'READ', None])

    def test_removed_words_count_as_negatives(self):
        result = experiment.metrics([{'label': 'MILK'}, {'label': 'READ'}], ['READ', 'READ'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['correct'], 1)
        self.assertEqual(result['negativeTotal'], 1)
        self.assertEqual(result['negativeFalse'], 1)

    def test_modified_protocol_fails_before_test_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / 'protocol.json'
            protocol.write_text(json.dumps({'labels': experiment.LABELS, 'threshold': .97}))
            (root / 'protocol.sha256').write_text(experiment.sha(protocol))
            protocol.write_text(json.dumps({'labels': experiment.LABELS, 'threshold': .1}))
            with patch.object(experiment, 'ROOT', root), self.assertRaisesRegex(ValueError, 'protocol changed'):
                experiment.verify()


if __name__ == '__main__':
    unittest.main()
