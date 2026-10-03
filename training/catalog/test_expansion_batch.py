import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
import train_expansion_batch as batch


class ExpansionTests(unittest.TestCase):
    def test_rejection_weight_is_validated_and_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            source.write_text(json.dumps([
                dict(label='MILK', split='train', participant='a', sha256='1', rawFrames=[], sequence=None),
                dict(label='MILK', split='val', participant='b', sha256='2', rawFrames=[], sequence=None),
            ]))
            for weight in (0, -1, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    batch.prepare(source, root / 'output', weight)
            batch.prepare(source, root / 'output', 10)
            self.assertEqual(json.loads((root / 'output/protocol.json').read_text())[
                'negativeExampleLossMultiplier'], 10)
            with self.assertRaises(ValueError):
                batch.prepare(source, root / 'output', 1)

    def test_expanded_head_accepts_last_word_but_rejects_unknown(self):
        with patch.object(batch.trainer, 'LABELS', batch.LABELS):
            self.assertEqual(tuple(batch.trainer.Net(16)(
                torch.zeros(2, 153, 32)).shape), (2, 11))
            probabilities = np.zeros((3, 11))
            probabilities[0, 9] = 1
            probabilities[1, 10] = 1
            probabilities[2, 9] = 1
            rows = [{'sequence': [[1]]}, {'sequence': [[1]]}, {'sequence': None}]
            self.assertEqual(batch.trainer.outputs(rows, probabilities, .8, .2),
                             ['MILK', None, None])

    def test_partition_and_duplicate_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            base = dict(label='MILK', rawFrames=[], sequence=None)
            for train, val in [
                (dict(split='train', participant='a', sha256='1'),
                 dict(split='val', participant='a', sha256='2')),
                (dict(split='train', participant='a', sha256='1'),
                 dict(split='val', participant='b', sha256='1')),
                (dict(split='train', participant='a', sha256='1'),
                 dict(split='test', participant='b', sha256='2')),
            ]:
                source.write_text(json.dumps([dict(base, **train), dict(base, **val)]))
                with self.assertRaises(ValueError):
                    batch.prepare(source, root / 'output')


if __name__ == '__main__':
    unittest.main()
