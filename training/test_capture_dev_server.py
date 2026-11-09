import unittest
from scripts.serve_capture_throughput_dev import byte_range

class CaptureDevelopmentRanges(unittest.TestCase):
    def test_closed_open_suffix_and_clipped_ranges(self):
        self.assertEqual(byte_range('bytes=2-5',10),(2,5))
        self.assertEqual(byte_range('bytes=2-',10),(2,9))
        self.assertEqual(byte_range('bytes=-3',10),(7,9))
        self.assertEqual(byte_range('bytes=0-99',10),(0,9))
    def test_invalid_and_unsatisfiable_ranges(self):
        for header in ['bytes=-','bytes=10-','bytes=4-2','bytes=-0','bytes=0-1,3-4','items=0-1']:
            with self.assertRaises(ValueError):byte_range(header,10)
