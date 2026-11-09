"""An interrupted test-source continuation is not a best-of accuracy run."""
import copy
import unittest
from scripts.merge_motion_source_recovery import merge


def sample(start, stop):
    report = dict(schema=1, geometry={}, recognitionLabels=198, indexSha256="index", bootstrapSha256="source",
                  runtimeSha256={}, activeModelSha256={}, calibrationSha256="calibration", activeAuxiliaryModelSha256={}, runnerSha256="runner",
                  isolation=dict(host="127.0.0.1", storage="in-memory only", realCameraCalls=0, microphoneCalls=0, getUserMediaCalls=1))
    report["attempts"] = [dict(id=str(i), number=i+1, stage="baseline 1×", rate=1, finishedAt="done", predicted=None, correct=False)
                          for i in range(start, stop)]
    return report


class SourceRecoveryTests(unittest.TestCase):
    def test_prefix_misses_and_all_continuation_misses_are_retained(self):
        a, b = sample(0, 153), sample(112, 198)
        original = copy.deepcopy(a)
        result = merge(a, b)
        self.assertEqual(len(result["attempts"]), 198)
        self.assertTrue(all(not row["correct"] for row in result["attempts"]))
        self.assertEqual(result["testSourceRecovery"]["outageAttemptsPreservedSeparately"], 41)
        self.assertEqual(a, original)
        self.assertIsNone(result["runnerSha256"])

    def test_duplicate_or_missing_continuation_is_rejected(self):
        for b in (sample(111, 198), sample(113, 198)):
            with self.assertRaises(ValueError):
                merge(sample(0, 153), b)

    def test_production_or_source_identity_change_is_rejected(self):
        for key in ("runtimeSha256", "bootstrapSha256", "calibrationSha256"):
            b = sample(112, 198)
            b[key] = "changed"
            with self.assertRaises(ValueError):
                merge(sample(0, 153), b)

    def test_unfinished_continuation_is_rejected(self):
        b = sample(112, 198)
        b["attempts"][-1]["finishedAt"] = None
        with self.assertRaises(ValueError):
            merge(sample(0, 153), b)


if __name__ == "__main__":
    unittest.main()
