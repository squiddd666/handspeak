"""Publishing cannot silently drop misses or change frozen evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publish_motion_release", ROOT / "scripts/publish_motion_release.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class MotionReleaseTests(unittest.TestCase):
    def mode(self):
        return {
            "accepted": {
                "attempts": 3, "correct": 1, "wrong": 1, "noMatch": 1, "tracked": 2,
                "negativeAttempts": 1, "negativeFalse": 1,
                "perLabel": {"A": {"total": 3, "correct": 1, "wrong": 1, "noMatch": 1,
                                    "tracked": 2, "syntheticGreeting": 0}},
            },
            "records": [
                {"file": "a1", "expected": "A", "prediction": "A", "outcome": "correct", "tracked": True, "syntheticGreeting": False},
                {"file": "a2", "expected": "A", "prediction": "B", "outcome": "wrong", "tracked": True, "syntheticGreeting": False},
                {"file": "a3", "expected": "A", "prediction": None, "outcome": "no-match", "tracked": False, "syntheticGreeting": False},
                {"file": "negative", "expected": "Z", "prediction": "A", "outcome": "wrong", "tracked": True, "syntheticGreeting": False},
            ],
        }

    def test_tracking_misses_stay_in_denominator(self):
        metrics = publisher.validate_mode(self.mode())
        self.assertEqual(metrics["attempts"], 3)
        self.assertEqual(metrics["noMatch"], 1)
        self.assertEqual(metrics["negativeFalse"], 1)

    def test_zero_accuracy_is_valid_measured_data(self):
        mode = self.mode()
        mode["records"][0].update(prediction=None, outcome="no-match")
        mode["accepted"].update(correct=0, noMatch=2)
        mode["accepted"]["perLabel"]["A"].update(correct=0, noMatch=2)
        self.assertEqual(publisher.validate_mode(mode)["correct"], 0)

    def test_tampered_summary_is_rejected(self):
        mode = self.mode()
        mode["accepted"]["correct"] += 1
        with self.assertRaises(ValueError):
            publisher.validate_mode(mode)

    def test_duplicate_attempts_are_rejected(self):
        mode = self.mode()
        mode["records"].append(copy.deepcopy(mode["records"][0]))
        with self.assertRaises(ValueError):
            publisher.validate_mode(mode)

    def test_empty_hands_cannot_be_counted_as_an_accepted_word(self):
        mode = self.mode()
        mode["records"][0]["tracked"] = False
        mode["accepted"].update(tracked=1)
        mode["accepted"]["perLabel"]["A"].update(tracked=1)
        with self.assertRaises(ValueError):
            publisher.validate_mode(mode)

    def test_false_accepts_cannot_be_omitted(self):
        mode = self.mode()
        mode["accepted"]["negativeFalse"] = 0
        with self.assertRaises(ValueError):
            publisher.validate_mode(mode)


if __name__ == "__main__":
    unittest.main()
