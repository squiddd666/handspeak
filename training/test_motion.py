"""Synthetic correctness checks, not an ASL recognition accuracy benchmark."""
import json
from pathlib import Path
import unittest
import quickjs
ROOT=Path(__file__).resolve().parents[1]
class MotionTests(unittest.TestCase):
    def setUp(self):
        self.js=quickjs.Context()
        self.js.eval((ROOT/'motion-model.js').read_text().replace('export ',''))
        self.js.eval('''
          function sequence(direction=1, speed=1){return Array.from({length:20},(_,i)=>[1,...Array.from({length:63},(_,c)=>c%3===0?direction*Math.pow(i/19,speed):c%3===1?c/100:0),...Array(64).fill(0)]);}
          const examples=[...Array.from({length:3},()=>({label:'FORWARD',sequence:sequence(1)})),...Array.from({length:3},()=>({label:'BACK',sequence:sequence(-1)}))];
        ''')
    def test_direction_and_speed(self):
        self.assertEqual(self.js.eval("recognizeMotion(sequence(1,1.3),examples).label"),'FORWARD')
        self.assertEqual(self.js.eval("recognizeMotion(sequence(-1),examples).label"),'BACK')
        self.assertGreater(self.js.eval('motionDistance(sequence(1),sequence(-1))'),.5)
    def test_unknown_ambiguous_and_insufficient_examples(self):
        self.assertIsNone(self.js.eval('recognizeMotion(sequence(10),examples)'))
        self.assertIsNone(self.js.eval('recognizeMotion(sequence(1),examples.slice(0,3))'))
        self.assertIsNone(self.js.eval("recognizeMotion(sequence(1),examples.map(e=>({...e,sequence:sequence(1)})))"))
        self.assertFalse(self.js.eval('validMotion([[NaN]])'))
        self.assertIsNone(self.js.eval('encodeMotion(Array.from({length:20},()=>[null,null]))'))
    def test_handedness_survives_detection_order_changes(self):
        self.js.eval('''
          const left=Array.from({length:21},()=>({x:.3,y:.5,z:0})),right=Array.from({length:21},()=>({x:.7,y:.5,z:0}));
          const a=motionFrame({landmarks:[left,right],handedness:[[{categoryName:'Left'}],[{categoryName:'Right'}]]});
          const b=motionFrame({landmarks:[right,left],handedness:[[{categoryName:'Right'}],[{categoryName:'Left'}]]});
        ''')
        self.assertTrue(self.js.eval('JSON.stringify(a)===JSON.stringify(b)'))
    def test_mirror_and_parameters(self):
        self.assertEqual(self.js.eval('motionDistance(sequence(),mirrorMotion(mirrorMotion(sequence())))'),0)
        self.assertEqual(self.js.eval("recognizeMotion(mirrorMotion(sequence()),examples,{maxDistance:.65,minRatio:1.3,minVotes:2,mirror:true}).label"),'FORWARD')
        self.assertFalse(self.js.eval('validMotionParameters({maxDistance:1,minRatio:1,minVotes:2,mirror:"true"})'))
    def test_trim_and_short_tracking_gaps(self):
        self.js.eval('''
          const hand=Array.from({length:21},(_,i)=>({x:.3+i*.01,y:.5,z:0}));
          const frames=Array.from({length:20},()=>[hand,null]);
          const padded=[[null,null],...frames,[null,null]];
          const gap=frames.map(f=>f.slice());gap[8]=[null,null];gap[9]=[null,null];
        ''')
        self.assertTrue(self.js.eval('JSON.stringify(encodeMotion(frames))===JSON.stringify(encodeMotion(padded))'))
        self.assertAlmostEqual(self.js.eval('motionDistance(encodeMotion(frames),encodeMotion(gap))'),0)
        self.assertIsNone(self.js.eval('encodeMotion(frames.map((f,i)=>i>3&&i<16?[null,null]:f))'))
    def test_portrait_and_landscape_geometry_match(self):
        self.js.eval('''
          const physical=Array.from({length:20},(_,t)=>[Array.from({length:21},(_,i)=>({x:.3+i*.01,y:.3+i*.007+t*.003,z:i*.001})),null]);
          function camera(aspect){return physical.map(frame=>frame.map(hand=>hand?.map(p=>({...p,y:p.y/aspect}))||null))}
        ''')
        self.assertAlmostEqual(self.js.eval('motionDistance(encodeMotion(camera(4/3),4/3),encodeMotion(camera(9/16),9/16))'),0)
    def boot_studio(self,pretrained=False,invalid=False):
        self.js.eval('''
          const elements={},stored={},timers=[];
          const document={querySelector:key=>elements[key]||=({value:'HELLO',disabled:false,checked:false,addEventListener(name,fn){this[name]=fn}})};
          const localStorage={getItem:key=>stored[key]||null,setItem:(key,value)=>{stored[key]=value}};
          const performance={now:()=>0};
          const console={warn(){}};
          function setTimeout(fn){timers.push(fn);return timers.length} function clearTimeout(){}
          let added=[],spoken=[];
        ''')
        if pretrained:
            self.js.eval('const fetch=async()=>({ok:true,json:async()=>({version:1,encoding:"two-hand-motion-v2",parameters:{maxDistance:.65,minRatio:1.3,minVotes:2,mirror:true},samples:examples'+('.slice(0,3)' if invalid else '')+'})});')
        else:self.js.eval('const fetch=async()=>({ok:false});')
        self.js.eval('\n'.join(l for l in (ROOT/'motion-studio.js').read_text().splitlines() if not l.startswith('import ')).replace('export ',''))
        self.js.eval('const studio=createMotionStudio({isRunning:()=>true,onWord:w=>added.push(w),onStatus:()=>{},speak:w=>spoken.push(w)});')
        model=json.loads((ROOT/'models/asl-knn.json').read_text())
        self.js.eval('const handFeatures='+json.dumps(model['samples'][0]['features'])+';')
        self.js.eval('''
          function record(label,direction,teach=true){
            document.querySelector('#motionLabel').value=label;elements[teach?'#motionTeach':'#motionRecognize'].click();
            for(let n=0;n<30;n++){
              const hand=Array.from({length:21},(_,i)=>({x:.5+handFeatures[i*3]*.05+direction*n*.003,y:.5+handFeatures[i*3+1]*.05,z:handFeatures[i*3+2]*.05}));
              studio.frame({landmarks:[hand],handedness:[[{categoryName:'Left'}]]},1500+n*80);
            }
            studio.frame({},4000);
          }
        ''')
        while self.js.execute_pending_job():pass
    def test_pretrained_ready_without_personal_training(self):
        self.boot_studio(pretrained=True)
        self.assertIn('2 pretrained words',self.js.eval("elements['#motionModelStatus'].textContent"))
        self.assertIn('no personal training required',self.js.eval("elements['#motionReady'].textContent"))
        self.js.eval("elements['#motionRecognize'].click();")
        self.assertTrue(self.js.eval("elements['#motionRecognize'].disabled"))
        self.js.eval("studio.cancel();elements['#motionLabel'].value='FORWARD';elements['#motionRemove'].click();")
        self.assertIn('FORWARD',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v2'])"))
    def test_invalid_pretrained_model_is_not_ready(self):
        self.boot_studio(pretrained=True,invalid=True)
        self.assertIn('unavailable',self.js.eval("elements['#motionModelStatus'].textContent"))
        self.js.eval("elements['#motionRecognize'].click();")
        self.assertIn('not ready',self.js.eval("elements['#motionHelp'].textContent"))
    def test_record_recognize_and_confirm_once(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('HELLO',1);record('BYE',-1)}")
        self.assertEqual(self.js.eval("JSON.parse(stored['handspeak-motion-v2']).length"),6)
        self.js.eval("record('',1,false);")
        self.assertEqual(self.js.eval('added.length'),0)
        self.assertFalse(self.js.eval("elements['#motionAccept'].disabled"))
        self.js.eval("document.querySelector('#motionAutoSpeak').checked=true;elements['#motionAccept'].click();elements['#motionAccept'].click();")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["HELLO"]')
        self.assertEqual(self.js.eval('JSON.stringify(spoken)'), '["HELLO"]')
    def test_cancel_and_no_hands_do_not_save(self):
        self.boot_studio()
        self.js.eval("elements['#motionTeach'].click();studio.cancel();")
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v2'])"))
        self.js.eval("elements['#motionTeach'].click();studio.frame({},4000);")
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v2'])"))
        self.assertIn('Not enough', self.js.eval("elements['#motionHelp'].textContent"))
if __name__=='__main__':unittest.main()
