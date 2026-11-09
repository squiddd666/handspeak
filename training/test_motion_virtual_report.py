"""Offline QA for the saved virtual-camera results; never opens a browser/device."""
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from scripts.summarize_motion_virtual_camera import assert_scalar_telemetry, normalized, tracked_frames


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/motion-virtual-camera-20261106"


def read(name):
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


class MotionVirtualReportTests(unittest.TestCase):
    def test_daily_report_does_not_reuse_previous_body_capture(self):
        take = {"family": "daily-manual", "request": {"sequenceFrames": 20},
                "camera": {"lastCapture": {"capture": "beginner", "trackedFrames": 8}}}
        self.assertIsNone(tracked_frames(take))
        take["camera"]["lastCapture"] = {"capture": "daily", "trackedFrames": 7}
        self.assertEqual(tracked_frames(take), 7)

    def test_manual_tracking_belongs_to_manual_route(self):
        take = {"family": "motion-manual", "camera": {"lastCapture": {"capture": "manual", "trackedFrames": 5}}}
        self.assertEqual(tracked_frames(take), 5)
        take["camera"]["lastCapture"]["capture"] = "capstone"
        self.assertIsNone(tracked_frames(take))

    def test_exactly_one_normal_speed_attempt_for_every_primary_reference(self):
        report = read("baseline-all-198.json")
        manifest = json.loads((ROOT / "models/recognition-videos.json").read_text(encoding="utf-8"))
        tests = [take for take in report["attempts"] if take["stage"] == "baseline 1×"]
        self.assertEqual(Counter(take["id"] for take in tests), Counter(item["id"] for item in manifest["items"]))
        self.assertEqual(len(tests), 198)
        self.assertTrue(all(take.get("finishedAt") and take["rate"] == 1 for take in tests))

    def test_failures_and_tracking_misses_stay_in_the_denominator(self):
        report, summary = read("baseline-all-198.json"), read("summary.json")
        tests = [take for take in report["attempts"] if take["stage"] == "baseline 1×"]
        correct = sum(bool(take.get("predicted")) and normalized(take["predicted"]) == normalized(take["label"])
                      for take in tests)
        self.assertEqual(summary["matched"], correct)
        self.assertEqual(summary["matched"] + summary["wrongPrediction"] + summary["noMatch"], 198)
        self.assertGreater(summary["noMatch"], 0)
        self.assertGreater(summary["wrongPrediction"], 0)
        self.assertGreater(summary["insufficientTrackingMisses"], 0)
        self.assertEqual(len(summary["words"]), 198)
        self.assertEqual(summary["sourceReportSha256"], hashlib.sha256((REPORTS / "baseline-all-198.json").read_bytes()).hexdigest())

    def test_no_physical_devices_or_raw_coordinate_exports(self):
        for filename in ["baseline-all-198.json", "badge-regressions.json", "badge-observations.json"]:
            assert_scalar_telemetry(read(filename))
        for filename in ["baseline-all-198.json", "badge-regressions.json"]:
            isolation = read(filename)["isolation"]
            self.assertEqual(isolation["host"], "127.0.0.1")
            self.assertEqual(isolation["storage"], "in-memory only")
            self.assertEqual(isolation["realCameraCalls"], 0)
            self.assertEqual(isolation["microphoneCalls"], 0)
        for bad in [{"landmarks": []}, {"pose": []}, {"frames": [[1, 2, 3]]}]:
            with self.assertRaises(ValueError):
                assert_scalar_telemetry(bad)

    def test_actual_predictions_display_their_correct_benchmark_family(self):
        observations = read("badge-observations.json")
        expected = {"capstoneFull": "Full 100-word", "beginner": "Beginner-79", "default": "Default six-word",
                    "daily": "Five-word server", "active category pack": "Pack words (DTW)", "capstoneCore": "Core 7-word"}
        self.assertEqual({item["expectedProfile"] for item in observations}, set(expected))
        for item in observations:
            self.assertTrue(item["badge"]["visible"])
            self.assertIn(expected[item["expectedProfile"]], item["badge"]["text"])
            self.assertNotIn("Not measured", item["badge"]["text"])
            self.assertIn("Live-camera accuracy is unverified", item["badge"]["scope"])
        slash = next(item for item in observations if item["take"]["label"] == "I / ME")
        self.assertEqual(slash["take"]["predicted"], "I / ME")
        numeric = next(item for item in observations if item["take"]["label"] == "8HOUR")
        self.assertFalse(numeric["take"]["correct"])

    def test_all_198_project_buttons_have_scores_without_starting_a_camera(self):
        ui = read("watch-learn-final-ui.json")
        buttons = [button for button in ui["buttons"] if button["id"] not in {"bye", "my", "buy"}]
        self.assertEqual(len(buttons), 198)
        self.assertEqual(ui["unmeasured"], [])
        self.assertIn("Start camera", ui["camera"])
        for button in buttons:
            self.assertRegex(button["score"], r"\d+(?:\.\d+)?% test · \d+/\d+")
        self.assertIn("198/198", ui["videoCoverage"])
        self.assertIn("198 of 198", ui["scoreCoverage"])


if __name__ == "__main__":
    unittest.main()
