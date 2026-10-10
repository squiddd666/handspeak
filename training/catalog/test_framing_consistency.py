import unittest
from check_framing_consistency import agreement


class ConsistencyTest(unittest.TestCase):
    def test_only_keeps_two_accepted_matching_decisions(self):
        self.assertEqual(agreement(['HOME', 'HOME', None, 'CALL', None],
                                   ['HOME', 'CALL', 'HOME', None, None]),
                         ['HOME', None, None, None, None])

    def test_rejects_incomplete_view(self):
        with self.assertRaises(ValueError):
            agreement(['HOME'], [])


if __name__ == '__main__':
    unittest.main()
