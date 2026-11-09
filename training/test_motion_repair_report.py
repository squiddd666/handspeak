"""All-word comparisons cannot count retries or omit incomplete attempts."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_motion_repair", ROOT / "scripts/report_motion_repair.py")
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class RepairReportTests(unittest.TestCase):
    def report(self):
        return {"attempts": [{"id": str(i), "stage": "baseline 1×", "rate": 1, "finishedAt": "done",
                              "correct": i < 69, "predicted": "WORD" if i < 92 else None}
                             for i in range(198)]}

    def test_every_attempt_is_counted_once(self):
        counts = reporter.counts(reporter.baseline_attempts(self.report()))
        self.assertEqual(counts, {"tested": 198, "matched": 69, "wrong": 23, "noMatch": 106})

    def test_slow_retry_does_not_inflate_baseline(self):
        report = self.report()
        report["attempts"].append({**report["attempts"][0], "stage": "slow retry", "rate": .5})
        self.assertEqual(len(reporter.baseline_attempts(report)), 198)

    def test_duplicate_or_missing_words_are_rejected(self):
        report = self.report()
        report["attempts"][-1]["id"] = "0"
        with self.assertRaises(ValueError):
            reporter.baseline_attempts(report)

    def test_unfinished_or_slow_baseline_is_rejected(self):
        for changes in [{"finishedAt": None}, {"rate": .5}]:
            report = self.report()
            report["attempts"][0].update(changes)
            with self.assertRaises(ValueError):
                reporter.baseline_attempts(report)


if __name__ == "__main__":
    unittest.main()
