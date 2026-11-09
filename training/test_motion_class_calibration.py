"""Class gates cannot use a practice target or erase sparse/error evidence."""
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT))
from calibrate_motion_classes import fit_classes
from motion_calibration import decide


class ClassCalibrationTests(unittest.TestCase):
    def test_gate_is_for_actual_top_class_only(self):
        policy = {'minScore': .8, 'classPolicies': {'A': {'minScore': .4}, 'B': {'minScore': .99}}}
        self.assertEqual(decide([.6, .4], ['A', 'B'], policy=policy)['predictions'][0]['label'], 'A')
        self.assertFalse(decide([.4, .6], ['A', 'B'], policy=policy)['predictions'])

    def test_missing_class_keeps_global_rejection(self):
        self.assertFalse(decide([.6, .4], ['A', 'B'], policy={'minScore': .8, 'classPolicies': {'B': {'minScore': .2}}})['predictions'])

    def test_class_can_recover_three_correct_with_no_extra_false_accept(self):
        p = np.asarray([[.65, .35]] * 3 + [[.4, .6]])
        fitted, audit = fit_classes(p, np.asarray(['A'] * 3 + ['__UNKNOWN__']), ['A', 'B'], ['A', 'B'], {'minScore': .8})
        self.assertEqual(fitted['validation']['correct'], 3)
        self.assertEqual(fitted['validation']['negativeFalse'], 0)
        self.assertIn('A', audit)

    def test_two_favorable_examples_cannot_relax_the_gate(self):
        fitted, audit = fit_classes(np.asarray([[.65, .35]] * 2), np.asarray(['A'] * 2), ['A', 'B'], ['A', 'B'], {'minScore': .8})
        self.assertFalse(audit)
        self.assertEqual(fitted['validation']['correct'], 0)

    def test_unknown_error_budget_cannot_be_relaxed(self):
        p = np.asarray([[.65, .35]] * 4)
        fitted, _ = fit_classes(p, np.asarray(['A'] * 3 + ['__UNKNOWN__']), ['A', 'B'], ['A', 'B'], {'minScore': .8})
        self.assertEqual(fitted['validation']['negativeFalse'], 0)
        self.assertEqual(fitted['validation']['correct'], 0)

    def test_tracking_misses_are_counted(self):
        p = np.asarray([[.9, .1], [np.nan, np.nan]])
        fitted, _ = fit_classes(p, np.asarray(['A', 'A']), ['A', 'B'], ['A', 'B'], {'minScore': .8})
        self.assertEqual(fitted['validation']['attempts'], 2)
        self.assertEqual(fitted['validation']['noMatch'], 1)


if __name__ == '__main__':unittest.main()
