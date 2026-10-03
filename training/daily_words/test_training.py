import unittest
import numpy as np
from train_citizen import LABELS,Net,outputs,metrics,gate
import torch
class DailyTrainingTests(unittest.TestCase):
 def test_public_recording_limit_expires_and_has_bounded_memory(self):
  from research_words import ResearchWords,ResearchError
  from unittest.mock import patch
  model=ResearchWords()
  with patch('research_words.time.monotonic',return_value=100):
   for _ in range(12):model.admit('test-client')
   with self.assertRaises(ResearchError) as error:model.admit('test-client')
   self.assertEqual(error.exception.status,429)
  with patch('research_words.time.monotonic',return_value=161):model.admit('test-client')
  self.assertEqual(len(model.requests),1)

 def test_untracked_and_unknown_are_never_accepted(self):
  rows=[{'sequence':None},{'sequence':[[1]]},{'sequence':[[1]]}]
  probs=np.array([[.99,.002,.002,.002,.002,.002],[.002,.002,.002,.002,.002,.99],[.99,.002,.002,.002,.002,.002]])
  self.assertEqual(outputs(rows,probs,.8,.2),[None,None,'NAME'])
 def test_gate_requires_all_words_and_zero_false_suggestions(self):
  rows=[{'label':l} for l in LABELS]+[{'label':'BOOK'}]
  good=metrics(rows,LABELS+[None]);self.assertTrue(gate(good))
  self.assertFalse(gate(metrics(rows,LABELS+['NAME'])))
  self.assertFalse(gate(metrics(rows,[None]+LABELS[1:]+[None])))
  m=metrics(rows,['HOME']+LABELS[1:]+[None]);self.assertEqual(m['wrong'],1);self.assertFalse(gate(m))
 def test_network_has_five_words_and_unknown_class(self):
  self.assertEqual(tuple(Net(16)(torch.zeros(2,153,32)).shape),(2,6))
if __name__=='__main__':unittest.main()
