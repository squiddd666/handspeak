import unittest
import numpy as np
from evaluate_ready_subset import predict, metrics


class ReadySubsetTests(unittest.TestCase):
    def test_excluded_winner_never_falls_back(self):
        protocol = dict(labels=['READY'], outputLabels=['READY', 'HELD'], threshold=.3, margin=.1)
        rows = [dict(sequence=[1]), dict(sequence=None), dict(sequence=[1])]
        actual = predict(rows, np.array([[.4,.6],[.9,.1],[.9,.1]]), protocol)
        self.assertEqual(actual, [None, None, 'READY'])

    def test_held_words_count_as_negatives_and_tracking_failures_as_misses(self):
        rows = [dict(label='READY'), dict(label='READY'), dict(label='HELD')]
        result = metrics(rows, ['READY',None,'READY'], ['READY'])
        self.assertEqual((result['total'],result['correct'],result['missed']), (2,1,1))
        self.assertEqual((result['negativeTotal'],result['negativeFalse']), (1,1))


if __name__ == '__main__': unittest.main()
