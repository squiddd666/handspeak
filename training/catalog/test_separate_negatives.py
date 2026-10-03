import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

import train_expansion_batch as batch


class SeparateNegativeTests(unittest.TestCase):
    def test_rejection_winner_never_falls_back_to_supported_runner_up(self):
        with patch.object(batch.trainer, 'LABELS', ['BOOK', 'CHAIR']):
            probs = np.array([[.4, .1, .5, 0], [.1, .1, 0, .8], [.9, .05, .025, .025]])
            rows = [{'sequence': [[1]]}]*3
            self.assertEqual(batch.trainer.outputs(rows, probs, .35, 0), [None, None, 'BOOK'])

    def test_protocol_freezes_class_order_and_requires_negative_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'data.json'
            rows = [dict(label=label, split=split, participant=split,
                         sha256=split+label, rawFrames=[], sequence=[[1]])
                    for split in ('train', 'val') for label in ('BOOK', 'HELLO', 'YES')]
            source.write_text(json.dumps(rows))
            batch.prepare(source, root / 'out', labels=['BOOK'], separate_negatives=True)
            protocol = json.loads((root / 'out/protocol.json').read_text())
            self.assertEqual(protocol['outputLabels'], ['BOOK', 'HELLO', 'YES'])
            self.assertEqual(batch.model_outputs(protocol, {'outputLabels': protocol['outputLabels']}),
                             ['BOOK', 'HELLO', 'YES'])
            with self.assertRaises(ValueError):
                batch.model_outputs(protocol, {'outputLabels': ['BOOK', 'YES', 'HELLO']})
            with self.assertRaises(ValueError):
                batch.prepare(source, root / 'out', labels=['BOOK'])
            rows.append(dict(rows[-1], label='ABSENT', sha256='new'))
            source.write_text(json.dumps(rows))
            with self.assertRaises(ValueError):
                batch.prepare(source, root / 'another', labels=['BOOK'], separate_negatives=True)

    def test_old_checkpoint_output_order_unchanged(self):
        self.assertEqual(batch.model_outputs({'labels': ['BOOK']}, {}), ['BOOK', batch.trainer.OTHER])


if __name__ == '__main__':
    unittest.main()
