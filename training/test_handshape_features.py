import unittest
import numpy as np
from handshape_features import frames_to_handshape, mirror, tensorize, raw_arrays


def frame():
    pose = [[.5,.3,0],[.45,.25,0],[.55,.25,0],[.35,.5,0],[.65,.5,0],[.3,.7,0],[.7,.7,0]]
    hand = [[.3+(i%4)*.025,.6-(i//4)*.03,-i*.003] for i in range(21)]
    return {"pose":pose,"left":hand,"right":None}


class HandshapeFeatureTests(unittest.TestCase):
    def test_contract(self):
        x=frames_to_handshape([frame() for _ in range(5)])
        self.assertEqual(x.shape,(146,32));self.assertEqual(x.dtype,np.float32)
        self.assertTrue(np.isfinite(x).all())
    def test_missing_side_stays_zero(self):
        x=frames_to_handshape([frame() for _ in range(5)])
        self.assertTrue((x[16:18]==0).all());self.assertTrue((x[81:144]==0).all())
        self.assertTrue((x[-1]==0).all())
    def test_gap_not_invented(self):
        frames=[frame() for _ in range(5)];frames[2]["left"]=None
        x=frames_to_handshape(frames,9)
        self.assertEqual(x[-2,4],0)
        self.assertTrue((x[14:16,4]==0).all());self.assertTrue((x[18:81,4]==0).all())
    def test_mirror_is_involution(self):
        x=frames_to_handshape([frame() for _ in range(5)])
        np.testing.assert_array_equal(mirror(mirror(x)),x)
        self.assertTrue((mirror(x)[-1]==1).all())
    def test_translation_and_size_invariant(self):
        a=[frame() for _ in range(5)];b=[frame() for _ in range(5)]
        for f in b:
            for field in ("pose","left"):
                for p in f[field]:
                    p[0]=p[0]*.7+.1;p[1]=p[1]*.7+.15;p[2]*=.7
        np.testing.assert_allclose(frames_to_handshape(a),frames_to_handshape(b),atol=2e-6)
    def test_pose_z_does_not_contaminate_hand_depth(self):
        a=[frame() for _ in range(5)];b=[frame() for _ in range(5)]
        for f in b:
            for p in f["pose"]:p[2]=10
        np.testing.assert_array_equal(frames_to_handshape(a),frames_to_handshape(b))
    def test_reject_invalid_and_untracked(self):
        self.assertIsNone(tensorize({"frames":[frame() for _ in range(4)]}))
        f=frame();f["left"]=None
        self.assertIsNone(tensorize({"frames":[f]*5}))
        f=frame();f["left"][3][2]=float("nan")
        with self.assertRaises(ValueError):raw_arrays([f])


if __name__=="__main__":unittest.main()
