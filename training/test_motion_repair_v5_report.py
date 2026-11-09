import unittest
from scripts.report_motion_repair_v5 import counts


class MotionRepairV5ReportTests(unittest.TestCase):
    def test_actual_output_counts_ignore_falsely_claimed_correctness(self):
        attempts=[dict(label='HELLO',predicted='DRINK',correct=True),
                  dict(label='THANK YOU',predicted=None,correct=True),
                  dict(label='BOOK',predicted='BOOK',correct=False)]
        self.assertEqual(counts(attempts),dict(attempts=3,matched=1,incorrect=1,noMatch=1))

    def test_no_match_is_not_called_a_correct_repair(self):
        self.assertEqual(counts([dict(label='HELLO',predicted=None)]),dict(attempts=1,matched=0,incorrect=0,noMatch=1))


if __name__=='__main__': unittest.main()
