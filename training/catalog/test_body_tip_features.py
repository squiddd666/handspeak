import copy
import json
from pathlib import Path
import unittest
import numpy as np
import quickjs
from body_tip_features import features, trainer


class BodyTipFeaturesTest(unittest.TestCase):
    def row(self, size=1):
        hand = [dict(x=.6+i*.01*size, y=.5+i*.002*size,z=i*.001*size) for i in range(21)]
        body = [dict(x=x,y=y,z=0,visibility=1) for x,y in [(.5,.2),(.3,.5),(.7,.5),(.2,.7),(.8,.7)]]
        return dict(rawFrames=[[hand,None]]*12,body=[body]*12,imageAspect=1)

    def test_preserves_information_missing_from_previous_encoding(self):
        small, large = self.row(1), self.row(2)
        self.assertTrue(np.allclose(trainer.encoding.features(small),trainer.encoding.features(large),atol=1e-6))
        self.assertFalse(np.allclose(features(small)[153:],features(large)[153:]))
        ratio = np.hypot(.12,.024)/.4
        self.assertAlmostEqual(float(features(small)[163,0]), ratio, places=6)
        self.assertAlmostEqual(float(features(large)[163,0]), ratio*2, places=6)

    def test_empty_hands_and_frames_are_finite(self):
        for frames in ([],[[None,None]]*12):
            result=features(dict(rawFrames=frames,body=[None]*len(frames),imageAspect=1))
            self.assertEqual(result.shape,(175,32))
            self.assertTrue(np.isfinite(result).all())
            self.assertTrue((result[153:]==0).all())

    def test_javascript_features_match_with_body_fallback_and_mirroring(self):
        context=quickjs.Context()
        root=Path(__file__).resolve().parents[1]/'accuracy'
        for name in ('temporal-browser.js','motion-residual-browser.js'):
            context.eval((root/name).read_text().replace('export ',''))
        a=self.row();b=copy.deepcopy(a);b['body']=[None]*12;b['imageAspect']=1.5
        for row in (a,b,trainer.encoding.mirrored(a)):
            expected=features(row)
            actual=np.array(json.loads(context.eval('JSON.stringify(bodyTipFeatures('+json.dumps(row)+'))')))
            self.assertLess(np.max(abs(actual-expected)),1e-6)


if __name__=='__main__':unittest.main()
