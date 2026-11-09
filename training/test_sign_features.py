"""Feature/capture-policy correctness, not a recognition accuracy benchmark."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sign_features import arrays, frames_to_tensor, mirror_tensor, tensorize, validate_capture
from motion_calibration import checkpoint_digest, decide, policy_for


def frame(left=True, right=False):
    return {"pose": [[.5, .15], [.46, .17], [.54, .17], [.3, .35], [.7, .35], [.2, .6], [.8, .6]],
        "left": [[.2 + i / 200, .5 + i / 300, 0] for i in range(21)] if left else None,
        "right": [[.7 + i / 200, .5 + i / 300, 0] for i in range(21)] if right else None}


class FeatureTests(unittest.TestCase):
    def test_missing_hand_is_zero_after_normalization(self):
        c, m = arrays([frame()], "masked-v2")
        self.assertTrue((c[:, 17:] == 0).all())
        self.assertTrue((m[:, 17:] == 0).all())
        legacy, _ = arrays([frame()], "legacy-v1")
        self.assertFalse((legacy[:, 17:] == 0).all())

    def test_gap_cannot_create_phantom_interpolated_hands(self):
        x = frames_to_tensor([frame(), frame(False), frame(), frame(False), frame()], "masked-v2")
        present = x[2:4, :, 7:].sum(0)
        self.assertTrue((x[:2, :, 7:][:, present == 0] == 0).all())
        # Observed points near a gap remain actual observations, not a path to the origin.
        original, _ = arrays([frame()], "masked-v2")
        for t in range(32):
            if present[t, 0]:
                np.testing.assert_allclose(x[:2, t, 7], original[0, 7], atol=1e-6)

    def test_anatomical_mirror_is_an_involution(self):
        x = frames_to_tensor([frame(True, True)] * 5, "masked-v2")
        mirrored = mirror_tensor(x, True)
        np.testing.assert_array_equal(mirror_tensor(mirrored, True), x)
        np.testing.assert_array_equal(mirrored[1, :, 3], x[1, :, 4])
        np.testing.assert_array_equal(mirrored[0, :, 3], -x[0, :, 4])

    def test_validation_rejects_malformed_or_nonfinite_landmarks(self):
        for mutation in [lambda f: f.update(left=[[0, 0]] * 20), lambda f: f["pose"][0].__setitem__(0, float("nan")),
                         lambda f: f.update(right=[[99, 0]] * 21)]:
            f = frame(); mutation(f)
            with self.assertRaises(ValueError):
                frames_to_tensor([f] * 5, "masked-v2")

    def test_legacy_feature_math_stays_compatible(self):
        f = frame(True, True)
        c = np.concatenate([np.asarray(f["pose"], np.float32), np.asarray(f["left"], np.float32)[[0, 4, 5, 8, 9, 12, 13, 16, 17, 20], :2],
            np.asarray(f["right"], np.float32)[[0, 4, 5, 8, 9, 12, 13, 16, 17, 20], :2]])
        c = (c - (c[3] + c[4]) / 2) / np.linalg.norm(c[3] - c[4])
        x = frames_to_tensor([f] * 5, "legacy-v1")
        np.testing.assert_allclose(x[:2, 0], c.T, atol=1e-6)

    def test_empty_hands_cannot_create_a_word_prediction(self):
        for frames in [[frame(False, False)] * 8, [frame()] * 4 + [frame(False, False)] * 4]:
            with self.assertRaisesRegex(ValueError, "hand-tracked"):
                validate_capture(frames)
            self.assertIsNone(tensorize({"frames": frames}, "masked-v2"))
        validate_capture([frame()] * 5)


class GateTests(unittest.TestCase):
    def test_policy_never_uses_expected_practice_word(self):
        result = decide([.7, .3], ["BAD", "GOOD"], policy={"minScore": .5})
        self.assertEqual(result["predictions"][0]["label"], "BAD")
        self.assertFalse(result["scoresAreCalibratedConfidence"])

    def test_restriction_does_not_inflate_a_tiny_outside_mass_into_a_match(self):
        result = decide([.02, .01, .97], ["BELT", "EAT", "OTHER"], allowed=[0, 1],
            policy={"minScore": .5, "minVocabularyMass": .1})
        self.assertFalse(result["predictions"])
        self.assertEqual(result["rejectionReason"], "outside-vocabulary")
        self.assertEqual(result["suggestions"][0]["label"], "BELT")

    def test_close_scores_remain_unaccepted_suggestions(self):
        result = decide([.51, .49], ["A", "B"], policy={"minScore": .4, "minMargin": .1})
        self.assertFalse(result["predictions"])
        self.assertEqual(result["rejectionReason"], "ambiguous")

    def test_checkpoint_change_invalidates_stale_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "weights.pt"; checkpoint.write_bytes(b"first weights")
            config = Path(folder) / "gates.json"
            config.write_text(json.dumps({"version": 1, "calibrationId": "validation-only", "models": {"beginner": {
                "checkpointSha256": checkpoint_digest(checkpoint), "policies": {"full": {"minScore": .35}}}}}), encoding="utf-8")
            with patch("motion_calibration.POLICIES", config):
                self.assertEqual(policy_for("beginner", checkpoint)["minScore"], .35)
                checkpoint.write_bytes(b"different weights")
                self.assertIsNone(policy_for("beginner", checkpoint))


if __name__ == "__main__":
    unittest.main()
