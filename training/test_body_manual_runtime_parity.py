import copy
import unittest
import numpy as np
from body_manual_features import tensorize, mirrored, dtw_many
from scripts.verify_body_manual_runtime import run_js, feature_error


def row(length=6):
    return dict(imageAspect=1,frames=[dict(pose=[[.5,.2],[.48,.2],[.52,.2],[.3,.4],[.7,.4],[.3,.6],[.7,.6]],
                left=[[.5+i*.002,.3+i*.003,i*.001] for i in range(21)],right=None) for _ in range(length)])


class BodyRuntimeParityTests(unittest.TestCase):
    def check_rows(self, rows):
        before=copy.deepcopy(rows)
        actual=run_js(rows)
        for source,result in zip(rows,actual):
            expected=tensorize(source)
            self.assertLessEqual(feature_error(expected,result['sequence']),1e-5)
            self.assertLessEqual(feature_error(mirrored(expected) if expected is not None else None,result['mirrored']),1e-5)
        self.assertEqual(rows,before)

    def test_aspect_and_two_coordinate_hands(self):
        a=row();b=row();b['imageAspect']=2
        for frame in b['frames']:
            for point in frame['pose']+frame['left']:point[1]/=2
            frame['left']=[p[:2] for p in frame['left']]
        self.check_rows([a,b])

    def test_masked_gaps_and_bankers_rounding(self):
        rows=[]
        for n in (6,20,39,58):
            a=row(n)
            for i,frame in enumerate(a['frames']):
                if i%4==1:frame['left']=None
                else:
                    for p in frame['left']:p[0]+=.005*i
                if i%4==2:frame['right']=copy.deepcopy(a['frames'][0]['left'])
            rows.append(a)
        self.check_rows(rows)

    def test_randomized_moving_shoulders_and_handshape(self):
        rng=np.random.default_rng(141)
        rows=[]
        for aspect in (.25,.75,1,1.75,5):
            a=row(32);a['imageAspect']=aspect
            for frame in a['frames']:
                frame['pose']=(np.asarray(frame['pose'])+rng.normal(0,.01,(7,2))).tolist()
                frame['left']=(np.asarray(frame['left'])+rng.normal(0,.002,(21,3))).tolist()
            rows.append(a)
        self.check_rows(rows)

    def test_invalid_inputs_and_blank_hands(self):
        a=row();a['frames']=a['frames'][:4]
        b=row();[f.update(left=None) for f in b['frames']]
        c=row();c['imageAspect']=None
        self.check_rows([a,b,c])

    def test_banded_distance_uses_the_same_weights_and_masks(self):
        a=row(10);a['frames'][3]['left']=None
        b=row(10)
        for frame in b['frames']:
            frame['right']=frame['left'];frame['left']=None
        x,y=tensorize(a),tensorize(b)
        weights=dict(wrist_weight=2,shape_weight=.25,pose_weight=.15,missing_cost=.5)
        actual=run_js([a],references=[x.tolist(),y.tolist()],weights=weights)[0]['distances']
        np.testing.assert_allclose(actual,dtw_many(x,[x,y],**weights),atol=1e-7,rtol=1e-7)


if __name__=='__main__': unittest.main()
