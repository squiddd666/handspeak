import copy
import unittest
from camera_framing import scaled
class CameraFramingTest(unittest.TestCase):
    def test_scales_depth_and_xy_without_inventing_visibility(self):
        row=dict(rawFrames=[[None,[dict(x=.7,y=.3,z=-.1)]],[None,None]],body=[None,None],sequence=None,participant='heldout',split='train')
        old=copy.deepcopy(row);out=scaled(row,.5)
        self.assertEqual(row,old);self.assertIsNone(out['sequence']);self.assertEqual(out['split'],'train')
        self.assertEqual(out['rawFrames'][1],[None,None]);self.assertIsNone(out['rawFrames'][0][0])
        point=out['rawFrames'][0][1][0]
        for key,value in dict(x=.6,y=.4,z=-.05).items():self.assertAlmostEqual(point[key],value)
    def test_rejects_body_and_invalid_scale(self):
        with self.assertRaises(ValueError):scaled(dict(body=[[]]),.5)
        for factor in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):scaled(dict(rawFrames=[],body=[]),factor)
if __name__=='__main__':unittest.main()
