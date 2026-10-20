"""Exercise real worker message flow with an injected detector failure."""
import json,re,unittest
from pathlib import Path
import quickjs
ROOT=Path(__file__).resolve().parents[1]
class WorkerTests(unittest.TestCase):
 def boot(self,cpu_fails=False):
  self.js=quickjs.Context();self.js.eval('''
   let messages=[],attempts=[],closed=0;const self={postMessage(data){messages.push(data)}};
   const preferredVisionDelegate=()=> 'GPU';const OffscreenCanvas=function(){};
   const ImageData=function(pixels,width,height){this.width=width;this.height=height};
   const mockVision={FilesetResolver:{forVisionTasks:async()=>({})},HandLandmarker:{createFromOptions:async(files,options)=>{const delegate=options.baseOptions.delegate;attempts.push(delegate);return {close(){closed++},detectForVideo(){if(delegate==='GPU'||CPU_FAILS)throw Error(delegate+' runtime failed');return {landmarks:[],handedness:[]}}}}}};
  '''.replace('CPU_FAILS',str(cpu_fails).lower()))
  source=(ROOT/'hand-detection-worker.js').read_text();source=re.sub(r"const \{preferredVisionDelegate\}=await import\([^;]+;",'',source);source=re.sub(r'const vision=await import\([^;]+;', 'const vision=mockVision;',source)
  self.js.eval(source);self.js.eval("self.onmessage({data:{type:'init'}})");self.drain()
 def drain(self):
  while self.js.execute_pending_job():pass
 def frame(self):
  self.js.eval("self.onmessage({data:{type:'frame',generation:7,timestamp:1000,width:1,height:1,pixels:new Uint8ClampedArray(4).buffer}})");self.drain()
 def test_gpu_failure_recovers_and_announces_cpu_delegate(self):
  self.boot();self.frame();messages=json.loads(self.js.eval('JSON.stringify(messages)'))
  self.assertEqual([m['type'] for m in messages],['ready','delegate','frame']);self.assertEqual(messages[1]['delegate'],'CPU');self.assertEqual(messages[2]['generation'],7);self.assertEqual(json.loads(self.js.eval('JSON.stringify(attempts)')),['GPU','CPU']);self.assertEqual(self.js.eval('closed'),1)
 def test_cpu_failure_is_reported_without_endless_retries(self):
  self.boot(cpu_fails=True);self.frame();messages=json.loads(self.js.eval('JSON.stringify(messages)'));self.assertEqual(messages[-1]['type'],'error');self.assertIn('CPU',messages[-1]['message']);self.assertEqual(self.js.eval('attempts.length'),2)
if __name__=='__main__':unittest.main()
