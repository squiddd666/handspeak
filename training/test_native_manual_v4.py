import sys,unittest
from pathlib import Path
import numpy as np
import quickjs
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from train_native_manual_v4 import dtw_many,mirrored,predictions,metrics


class ManualRepairTests(unittest.TestCase):
    def test_vectorized_dtw_matches_on_device_math(self):
        rng=np.random.default_rng(123)
        a=rng.normal(0,.2,(20,128));b=rng.normal(0,.2,(20,128))
        a[:,[0,64]]=rng.integers(0,2,(20,2));b[:,[0,64]]=rng.integers(0,2,(20,2))
        js=quickjs.Context();js.eval((ROOT/'motion-model.js').read_text().replace('export ',''))
        value=js.eval('motionDistance('+json.dumps(a.tolist())+','+json.dumps(b.tolist())+')')
        self.assertAlmostEqual(float(dtw_many(a,[b])[0]),value,places=10)
        flipped=json.loads(js.eval('JSON.stringify(mirrorMotion('+json.dumps(a.tolist())+'))'))
        np.testing.assert_array_equal(mirrored(a),flipped)

    def test_unsupported_competitor_is_never_emitted(self):
        refs=[dict(label='A'),dict(label='A'),dict(label='OTHER MOVEMENT')]
        params=dict(maxDistance=.65,minRatio=1.1,minVotes=2,strongRatio=2.)
        out=predictions(np.asarray([[.8,.9,.1],[.1,.11,.9],[np.inf]*3]),refs,params,['A'])
        self.assertEqual(out,[None,'A',None])

    def test_tracking_misses_stay_in_denominator(self):
        rows=[dict(label='A'),dict(label='A'),dict(label='OTHER')]
        m=metrics(rows,['A',None,None],['A'])
        self.assertEqual((m['attempts'],m['correct'],m['noMatch'],m['negativeAttempts']),(2,1,1,1))


if __name__=='__main__':unittest.main()
