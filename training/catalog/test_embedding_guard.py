import unittest
import numpy as np
from train_embedding_guard import apply_guard
class EmbeddingGuardTest(unittest.TestCase):
    def test_guard_only_removes_suggestions(self):
        guard=dict(mean=[0,0],scale=[1,1],centers=[[0,0],[2,2]],centerLabels=['A','OTHER'],radiusByLabel={'A':.2})
        # Matching in-distribution A, rejected OOD A, negative-class nearest A,
        # and an already-rejected input must never become a new word.
        values=np.array([[.1,.1],[8,8],[1.9,1.9],[0,0]])
        self.assertEqual(apply_guard(['A','A','A',None],values,guard),['A',None,None,None])
if __name__=='__main__':unittest.main()
