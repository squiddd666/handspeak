"""Anatomical hand assignment checks without running inference or opening a camera."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extract_reference_motion import assign_hands, update_cached_slots


def pose(left=(.7, .5), right=(.3, .5)):
    points = [[.5, .5, 0., 1.] for _ in range(33)]
    points[11], points[12] = [.7, .3, 0., 1.], [.3, .3, 0., 1.]
    points[15], points[16] = [*left, 0., 1.], [*right, 0., 1.]
    return points


def hand(x, y, label, score=.95):
    return {"landmarks": [[x, y, 0.] for _ in range(21)], "label": label, "score": score}


class ReferenceTrackingTests(unittest.TestCase):
    def test_crossing_hands_keep_anatomical_identity_not_screen_x(self):
        left, right = hand(.3, .5, "Left"), hand(.7, .5, "Right")
        result = assign_hands([right, left], pose(left=(.3, .5), right=(.7, .5)), {}, 480, 640)
        self.assertIs(result["Left"], left)
        self.assertIs(result["Right"], right)

    def test_lower_supporting_hand_is_not_discarded(self):
        left, right = hand(.7, .7, "Left"), hand(.3, .2, "Right")
        result = assign_hands([left, right], pose(left=(.7, .7), right=(.3, .2)), {}, 480, 640)
        self.assertEqual(set(result), {"Left", "Right"})

    def test_single_hand_cannot_fill_both_slots(self):
        result = assign_hands([hand(.3, .5, "Right")], pose(), {}, 480, 640)
        self.assertEqual(set(result), {"Right"})

    def test_pose_anchor_overrules_wrong_classifier_label(self):
        result = assign_hands([hand(.3, .5, "Left")], pose(), {}, 480, 640)
        self.assertEqual(set(result), {"Right"})

    def test_border_hand_and_out_of_frame_other_wrist_do_not_swap_sides(self):
        p = pose(left=(.9, 1.18), right=(-.032, .556))
        result = assign_hands([hand(.034, .396, "Left")], p, {}, 480, 640)
        self.assertEqual(set(result), {"Right"})

    def test_unknown_detection_is_not_guessed_from_screen_half(self):
        self.assertEqual(assign_hands([hand(.1, .5, "", .2)], None, {}, 480, 640), {})

    def test_cached_slots_can_be_repaired_without_retracking_video(self):
        right = hand(.3, .5, "Right")
        record = {"reference": {"width": 480, "height": 640}, "frames": [
            {"time": 0., "pose": pose(), "hands": {"Left": right}},
            {"time": 2., "pose": pose(left=(.3, .5), right=(.7, .5)), "hands": {"Right": hand(.3, .5, "Left")}},
        ]}
        updated = update_cached_slots(record)
        self.assertEqual(set(updated["frames"][0]["hands"]), {"Right"})
        self.assertEqual(set(updated["frames"][1]["hands"]), {"Left"})


if __name__ == "__main__":
    unittest.main()
