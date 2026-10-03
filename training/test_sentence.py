"""Sentence editing invariants, not an ASL translation benchmark."""
import unittest
from pathlib import Path
import quickjs
class SentenceTests(unittest.TestCase):
 def setUp(self):
  self.js=quickjs.Context();self.js.eval((Path(__file__).resolve().parents[1]/'sentence-builder.js').read_text().replace('export ',''))
 def test_words_spacing_and_repeat(self):
  self.assertEqual(self.js.eval("appendWord(appendWord('I  ', ' AM '), 'HUNGRY')"),'I AM HUNGRY')
  self.assertEqual(self.js.eval("appendWord('GO', 'GO')"),'GO GO')
 def test_punctuation_and_undo(self):
  self.assertEqual(self.js.eval("finishSentence('I AM HUNGRY  ')"),'I AM HUNGRY.')
  self.assertEqual(self.js.eval("finishSentence('FOOD.', '?')"),'FOOD?')
  self.assertEqual(self.js.eval("removeLastWord('I AM HUNGRY. ')"),'I AM')
  self.assertEqual(self.js.eval("removeLastWord('HELLO')"),'')
  self.assertEqual(self.js.eval("finishSentence('')"),'')
 def test_limit_never_silently_truncates(self):
  self.assertIsNone(self.js.eval("appendWord('X'.repeat(999), 'GO')"))
  self.assertIsNone(self.js.eval("finishSentence('X'.repeat(1000))"))
  self.assertEqual(self.js.eval("finishSentence('X'.repeat(999)+'.','?').length"),1000)
if __name__=='__main__':unittest.main()
