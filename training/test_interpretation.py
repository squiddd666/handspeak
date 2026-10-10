"""Gateway safety, capacity, and error handling; model quality has separate live probes."""
import sys,json,unittest,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from interpretation import Interpreter,InterpretationError
class InterpretationTests(unittest.TestCase):
 def setUp(self):
  self.i=Interpreter();self.i.enabled=True;self.calls=[]
  def request(path,payload=None,timeout=45):
   self.calls.append(payload);return {'done':True,'done_reason':'stop','response':json.dumps({'sentence':'I want water, please.','note':'Review it.','needsClarification':False})}
  self.i.request=request
 def test_text_only_local_request_and_original_preserved(self):
  r=self.i.interpret('I WANT WATER PLEASE','a');self.assertEqual(r['original'],'I WANT WATER PLEASE');self.assertEqual(r['sentence'],'I want water, please.')
  payload=self.calls[0];self.assertFalse(payload['think']);self.assertFalse(payload['stream']);self.assertNotIn('images',payload);self.assertEqual(json.loads(payload['prompt']),{'draft':'I WANT WATER PLEASE'})
  self.assertEqual(payload['keep_alive'],-1)
 def test_warmup_is_local_synthetic_and_shares_capacity(self):
  started=threading.Event();release=threading.Event();done=threading.Event()
  def request(path,payload=None,timeout=45):
   self.calls.append(payload);started.set();release.wait(2);done.set();raise TimeoutError()
  self.i.request=request
  self.assertTrue(self.i.warmup());self.assertTrue(started.wait(1));self.assertTrue(self.i.warming)
  self.assertEqual(json.loads(self.calls[0]['prompt']),{'draft':'HELLO'})
  self.assertFalse(self.i.warmup())
  with self.assertRaises(InterpretationError) as e:self.i.interpret('WATER PLEASE','a')
  self.assertIn('warming up',str(e.exception));release.set();self.assertTrue(done.wait(1))
  for thread in threading.enumerate():
   if thread.name=='sentence-model-warmup':thread.join(1)
  self.assertFalse(self.i.warming);self.assertTrue(self.i.slot.acquire(False));self.i.slot.release()
 def test_validation_disabled_rate_limit_busy(self):
  for value in [None,True,'',' ','x'*501,'bad\0']:
   with self.assertRaises(InterpretationError) as e:self.i.interpret(value,'a')
   self.assertEqual(e.exception.status,422)
  self.i.enabled=False
  with self.assertRaises(InterpretationError) as e:self.i.interpret('HELLO','a')
  self.assertEqual(e.exception.status,503);self.i.enabled=True
  self.i.slot.acquire()
  with self.assertRaises(InterpretationError) as e:self.i.interpret('HELLO','a')
  self.assertEqual(e.exception.status,503);self.i.slot.release()
  for _ in range(3):self.i.interpret('HELLO','a')
  with self.assertRaises(InterpretationError) as e:self.i.interpret('HELLO','a')
  self.assertEqual(e.exception.status,429)
 def test_negation_and_numbers_are_not_silently_dropped(self):
  for text in ['I NO WANT WATER','I WANT 2 WATER']:
   r=self.i.interpret(text,'a');self.assertTrue(r['needsClarification']);self.assertEqual(r['sentence'],'')
 def test_bad_output_and_timeout_release_capacity(self):
  for reply in [[],{'done':False}, {'done':True,'done_reason':'length'}, {'done':True,'response':'{}'}, {'done':True,'response':'not json'}, {'done':True,'response':json.dumps({'sentence':5,'needsClarification':False,'note':''})}]:
   self.i.attempts.clear();self.i.request=lambda *a,**k:reply
   with self.assertRaises(InterpretationError):self.i.interpret('HELLO','a')
   self.assertTrue(self.i.slot.acquire(False));self.i.slot.release()
  def fail(*a,**k):raise TimeoutError()
  self.i.request=fail;self.i.attempts.clear()
  with self.assertRaises(InterpretationError) as e:self.i.interpret('HELLO','a')
  self.assertEqual(e.exception.status,503)
 def test_clarification_has_no_applyable_sentence(self):
  self.i.request=lambda *a,**k:{'done':True,'response':json.dumps({'sentence':'invented','needsClarification':True,'note':'Who is hungry?'})}
  r=self.i.interpret('HUNGRY GO','a');self.assertEqual(r['sentence'],'');self.assertEqual(r['note'],'Who is hungry?')
if __name__=='__main__':unittest.main()
