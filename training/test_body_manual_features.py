import unittest
import numpy as np
from body_manual_features import dtw_many, tensorize, mirrored


def row(aspect=1):
    pose = [[.5,.2],[.48,.2],[.52,.2],[.3,.4],[.7,.4],[.3,.6],[.7,.6]]
    hand = [[.5+i*.002, .3+i*.003, i*.001] for i in range(21)]
    return dict(imageAspect=aspect, frames=[dict(pose=pose, left=hand, right=None) for _ in range(6)])


class BodyManualFeatureTests(unittest.TestCase):
    def test_aspect_units_are_equivalent(self):
        a, b = row(1), row(2)
        # Inputs share their coordinate arrays inside one synthetic clip.
        b["frames"][0]["pose"][:] = [[x,y/2] for x,y in b["frames"][0]["pose"]]
        b["frames"][0]["left"][:] = [[x,y/2,z] for x,y,z in b["frames"][0]["left"]]
        np.testing.assert_allclose(tensorize(a), tensorize(b), atol=1e-6)

    def test_missing_hands_remain_zero(self):
        x = tensorize(row())
        self.assertEqual(x.shape, (20,146))
        self.assertTrue(np.all(x[:,16:18] == 0))
        self.assertTrue(np.all(x[:,81:144] == 0))
        self.assertTrue(np.all(x[:,-1] == 0))

    def test_mirror_is_an_involution(self):
        x = tensorize(row())
        np.testing.assert_allclose(mirrored(mirrored(x)), x)

    def test_identical_motion_has_zero_distance(self):
        x = tensorize(row())
        self.assertLess(dtw_many(x, [x])[0], 1e-7)

    def test_absolute_body_location_is_not_erased(self):
        a, b = row(), row()
        for point in b["frames"][0]["left"]:
            point[1] += .2
        self.assertGreater(dtw_many(tensorize(a), [tensorize(b)])[0], .1)

    def test_invalid_aspect_and_tiny_capture_fail(self):
        for aspect in (0, float('nan'), None):
            self.assertIsNone(tensorize(row(aspect)))
        a = row()
        a['frames'] = a['frames'][:2]
        self.assertIsNone(tensorize(a))


if __name__ == '__main__':
    unittest.main()
