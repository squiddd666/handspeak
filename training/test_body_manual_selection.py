import itertools
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from train_body_manual_v5 import gate_mask, gate_statistics
from train_native_manual_v4 import predictions


class BodyManualSelectionTests(unittest.TestCase):
    def test_vectorized_gates_match_original_including_missing_and_ties(self):
        rng = np.random.default_rng(73)
        distances = rng.uniform(0, 4, (60, 8))
        distances[0] = np.inf
        distances[1] = 0
        distances[2, :3] = .5
        distances[3, 1:] = np.inf
        refs = [{'label': label} for label in ['A', 'B', 'A', 'OTHER MOVEMENT', 'B', 'C', 'C', 'OTHER MOVEMENT']]
        labels = ['A', 'B', 'C']
        statistics = gate_statistics(distances, refs, labels)
        for limit, ratio, votes, strong in itertools.product((.2, .5, 1.5, 3), (1, 1.2, 2), (1, 2, 3), (1.5, 3, 5)):
            p = dict(maxDistance=limit, minRatio=ratio, minVotes=votes, strongRatio=strong)
            actual = [str(label) if accepted else None for label, accepted in zip(statistics[0], gate_mask(statistics, p))]
            self.assertEqual(actual, predictions(distances, refs, p, labels))


if __name__ == '__main__':
    unittest.main()
