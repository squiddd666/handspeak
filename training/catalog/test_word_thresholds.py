import unittest
import numpy as np
from calibrate_word_thresholds import predictions
class WordThresholdTest(unittest.TestCase):
    def test_stricter_word_cutoff_never_uses_runner_up(self):
        p=dict(labels=['A','B'],outputLabels=['A','B','OTHER'],threshold=.8,thresholdByLabel={'A':.9,'B':.8},margin=0)
        rows=[dict(sequence=[1]) for _ in range(5)]
        probs=np.array([[.85,.1,.05],[.91,.05,.04],[.1,.81,.09],[.1,.05,.85],[.4,.5,.1]])
        self.assertEqual(predictions(rows,probs,p),[None,'A','B',None,None])
    def test_quality_and_margin_rejection_survive_calibration(self):
        p=dict(labels=['A'],outputLabels=['A','OTHER'],threshold=.8,thresholdByLabel={'A':.9},margin=.95)
        self.assertEqual(predictions([dict(sequence=[1]),dict(sequence=None)],np.array([[.91,.09],[.999,.001]]),p),[None,None])
if __name__=='__main__':unittest.main()
