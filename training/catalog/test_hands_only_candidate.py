import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
import evaluate_hands_only_candidate as candidate


class HandsOnlyCandidateTest(unittest.TestCase):
    def run_prediction(self, winner, usable=True):
        torch.set_num_threads(1)
        model=candidate.MotionNet(2,torch.zeros(175),torch.ones(175)).eval()
        with torch.no_grad():
            for parameter in model.parameters():parameter.zero_()
            model.head[1].bias[winner]=10
        protocol=dict(outputLabels=['SUPPORTED','OTHER'],labels=['SUPPORTED'],threshold=.65,margin=0)
        hand=[dict(x=.3,y=.4,z=0) for _ in range(21)]
        row=dict(rawFrames=[[hand,None]]*12,body=[{'private':'body data'}]*12,
                 sequence=[1] if usable else None)
        original=copy.deepcopy(row)
        def features(clean):
            self.assertTrue(all(body is None for body in clean['body']))
            return np.zeros((175,32),dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.pt'
            torch.save(dict(outputLabels=protocol['outputLabels'],states=[model.state_dict()]),path)
            with patch.object(candidate.body_tip_features,'features',side_effect=features):
                result=candidate.predict([row],path,protocol)
        self.assertEqual(row,original)
        return result

    def test_excluded_winner_never_falls_back(self):
        self.assertEqual(self.run_prediction(1),[None])

    def test_quality_rejection_preserved(self):
        self.assertEqual(self.run_prediction(0),['SUPPORTED'])
        self.assertEqual(self.run_prediction(0,usable=False),[None])


if __name__=='__main__':unittest.main()
