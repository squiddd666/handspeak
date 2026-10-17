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
        self.js.eval('\n'.join(l for l in (ROOT/'expanded-motion.js').read_text().splitlines() if not l.startswith('import ')).replace('export ',''))
        self.js.eval((ROOT/'automatic-motion.js').read_text().replace('export ',''))
        self.js.eval('''
          let hiddenLabel=null;const isWordEnabled=label=>label!==hiddenLabel;
          function sequence(direction=1, speed=1){return Array.from({length:20},(_,i)=>[1,...Array.from({length:63},(_,c)=>c%3===0?direction*Math.pow(i/19,speed):c%3===1?c/100:0),...Array(64).fill(0)]);}
          const examples=[...Array.from({length:3},()=>({label:'FORWARD',sequence:sequence(1)})),...Array.from({length:3},()=>({label:'BACK',sequence:sequence(-1)}))];
        ''')
    def test_expansion_preserves_existing_match_and_is_optional(self):
        self.js.eval("const strict={maxDistance:.1,minRatio:1.3,minVotes:2,mirror:false};const extra={labels:['FAR'],parameters:strict,samples:Array.from({length:3},()=>({label:'FAR',sequence:sequence(3)}))};")
        self.assertEqual(self.js.eval("recognizeExpandedMotion(sequence(1),examples,strict,extra).label"),'FORWARD')
        self.assertIsNone(self.js.eval("recognizeExpandedMotion(sequence(3),examples,strict,null)"))
        self.assertEqual(self.js.eval("recognizeExpandedMotion(sequence(3),examples,strict,extra).label"),'FAR')
        self.assertIsNone(self.js.eval("recognizeExpandedMotion(sequence(30),examples,strict,extra)"))
    def test_extra_download_failure_preserves_original_vocabulary(self):
        self.boot_studio(pretrained=True)
        self.assertIn('2 pretrained words',self.js.eval("elements['#motionModelStatus'].textContent"))
        self.assertIn('could not load',self.js.eval("elements['#expandedWordsStatus'].textContent"))
        self.assertIn('FORWARD',self.js.eval("elements['#motionLibrary'].textContent"))
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
    def test_coherent_sign_survives_isolated_edge_detections(self):
        self.js.eval('''
          const hand=Array.from({length:21},(_,i)=>({x:.3+i*.01,y:.4,z:0}));
          const pattern='XX......XXXXXXXXXXXXXXXX.....X';
          const clip=Array.from(pattern,c=>c==='X'?[hand,null]:[null,null]);
        ''')
        self.assertTrue(self.js.eval('validMotion(encodeMotion(clip))'))
        self.assertIsNone(self.js.eval("encodeMotion(Array.from('XXXXXXXX..........XXXXXXXX',c=>c==='X'?[hand,null]:[null,null]))"))
    def test_whole_movement_is_centered(self):
        self.js.eval('''
          const moving=Array.from({length:20},(_,t)=>[Array.from({length:21},(_,i)=>({x:.2+i*.01+t*.008,y:.4,z:0})),null]);
          const encoded=encodeMotion(moving);
        ''')
        self.assertAlmostEqual(self.js.eval('encoded.reduce((sum,f)=>sum+f[1],0)/20'),0)
        self.assertLess(self.js.eval('encoded[0][1]'),0)
        self.assertGreater(self.js.eval('encoded[19][1]'),0)
    def test_clear_sparse_match_can_pass_without_two_nearby_votes(self):
        self.js.eval("const sparse=[{label:'A',sequence:sequence(1)},{label:'A',sequence:sequence(8)},{label:'A',sequence:sequence(9)},...Array.from({length:3},()=>({label:'B',sequence:sequence(-1)}))];")
        self.assertIsNone(self.js.eval('recognizeMotion(sequence(1),sparse)'))
        self.assertEqual(self.js.eval("recognizeMotion(sequence(1),sparse,{maxDistance:.65,minRatio:1,minVotes:2,mirror:false,strongRatio:1.5}).label"),'A')
        self.assertIsNone(self.js.eval("recognizeMotion(sequence(100),sparse,{maxDistance:.65,minRatio:1,minVotes:2,mirror:false,strongRatio:1.5})"))
    def boot_studio(self,pretrained=False,invalid=False):
        self.js.eval('''
          const elements={},stored={},timers=[];
          const document={querySelector:key=>elements[key]||=({value:'HELLO',disabled:false,checked:false,addEventListener(name,fn){this[name]=fn}})};
          const localStorage={getItem:key=>stored[key]||null,setItem:(key,value)=>{stored[key]=value}};
          const performance={now:()=>0};
          const console={warn(){}};
          function setTimeout(fn){timers.push(fn);return timers.length} function clearTimeout(){}
          let added=[],spoken=[],finishEnabled=false,finishCalls=0;
        ''')
        if pretrained:
            self.js.eval('const fetch=async()=>({ok:true,json:async()=>({version:1,encoding:"two-hand-motion-v3",parameters:{maxDistance:.65,minRatio:1.3,minVotes:2,mirror:true},samples:examples'+('.slice(0,3)' if invalid else '')+'})});')
        else:self.js.eval('const fetch=async()=>({ok:false});')
        self.js.eval('\n'.join(l for l in (ROOT/'temporal-word-model.js').read_text().splitlines() if not l.startswith('import ')).replace('export ',''))
        self.js.eval('\n'.join(l for l in (ROOT/'motion-studio.js').read_text().splitlines() if not l.startswith('import ')).replace('export ',''))
        self.js.eval('const studio=createMotionStudio({isRunning:()=>true,onWord:w=>added.push(w),onStatus:()=>{},speak:w=>spoken.push(w),onFinish:()=>{if(!finishEnabled)return false;finishCalls++;return true;}});')
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
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v3'])"))
    def test_category_switch_resets_capture_and_restores_default(self):
        self.boot_studio(pretrained=True)
        self.js.eval("const category={version:1,encoding:'two-hand-motion-v3',labels:['NEW'],parameters:{maxDistance:.65,minRatio:1.3,minVotes:2,mirror:false},samples:examples.map(e=>({...e,label:e.label==='FORWARD'?'NEW':'OTHER MOVEMENT'}))};studio.recognize();")
        self.assertTrue(self.js.eval('studio.isCapturing()'))
        self.assertTrue(self.js.eval("studio.setVocabulary(category,'Actions')"))
        self.assertFalse(self.js.eval('studio.isCapturing()'))
        self.assertTrue(self.js.eval("elements['#expandedWords'].disabled"))
        self.assertIn('NEW',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertNotIn('OTHER MOVEMENT',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertNotIn('FORWARD',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertFalse(self.js.eval("studio.setVocabulary({...category,encoding:'bad'},'bad')"))
        self.assertIn('NEW',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertTrue(self.js.eval('studio.setVocabulary(null)'))
        self.assertIn('FORWARD',self.js.eval("elements['#motionLibrary'].textContent"))
        self.assertNotIn('NEW',self.js.eval("elements['#motionLibrary'].textContent"))
    def test_category_negative_reference_never_becomes_a_word(self):
        self.boot_studio(pretrained=True)
        self.js.eval("""
          function clip(direction){return encodeMotion(Array.from({length:30},(_,n)=>[Array.from({length:21},(_,i)=>({x:.5+handFeatures[i*3]*.05+direction*n*.003,y:.5+handFeatures[i*3+1]*.05,z:handFeatures[i*3+2]*.05})),null]));}
          const model={version:1,encoding:'two-hand-motion-v3',labels:['NEW'],parameters:{maxDistance:.65,minRatio:1.3,minVotes:2,mirror:false},samples:[...Array.from({length:3},()=>({label:'NEW',sequence:clip(1)})),...Array.from({length:3},()=>({label:'OTHER MOVEMENT',sequence:clip(-1)}))]};
          studio.setVocabulary(model,'Test');record('',-1,false);
        """)
        self.assertTrue(self.js.eval("elements['#motionAccept'].disabled"))
        self.assertEqual(self.js.eval('added.length'),0)
        self.js.eval("record('',1,false);elements['#motionAccept'].click();")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["NEW"]')
    def test_invalid_pretrained_model_is_not_ready(self):
        self.boot_studio(pretrained=True,invalid=True)
        self.assertIn('unavailable',self.js.eval("elements['#motionModelStatus'].textContent"))
        self.js.eval("elements['#motionRecognize'].click();")
        self.assertIn('not ready',self.js.eval("elements['#motionHelp'].textContent"))
    def test_record_recognize_and_confirm_once(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('HELLO',1);record('BYE',-1)}")
        self.assertEqual(self.js.eval("JSON.parse(stored['handspeak-motion-v3']).length"),6)
        self.js.eval("record('',1,false);")
        self.assertEqual(self.js.eval('added.length'),0)
        self.assertFalse(self.js.eval("elements['#motionAccept'].disabled"))
        self.js.eval("document.querySelector('#motionAutoSpeak').checked=true;elements['#motionAccept'].click();elements['#motionAccept'].click();")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["HELLO"]')
        self.assertEqual(self.js.eval('JSON.stringify(spoken)'), '["HELLO"]')
    def test_sentence_auto_add_is_opt_in_once_and_never_speaks(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('HELLO',1);record('BYE',-1)}")
        self.js.eval("document.querySelector('#sentenceAutoAdd').checked=true;document.querySelector('#motionAutoSpeak').checked=true;record('',1,false);")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["HELLO"]')
        self.assertEqual(self.js.eval('spoken.length'),0)
        self.js.eval("elements['#motionAccept'].click();")
        self.assertEqual(self.js.eval('added.length'),1)
        self.assertTrue(self.js.eval("elements['#motionAccept'].disabled"))
    def test_finish_command_consumes_match_only_when_enabled(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('FINISH',1);record('BYE',-1)}")
        self.js.eval("finishEnabled=true;document.querySelector('#sentenceAutoAdd').checked=true;record('',1,false);")
        self.assertEqual(self.js.eval('finishCalls'),1)
        self.assertEqual(self.js.eval('added.length'),0)
        self.assertEqual(self.js.eval('spoken.length'),0)
        self.assertTrue(self.js.eval("elements['#motionAccept'].disabled"))
        self.js.eval("finishEnabled=false;record('',1,false);")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["FINISH"]')

    def test_enabling_auto_add_preserves_pending_word_once(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('HELLO',1);record('BYE',-1)}record('',1,false);")
        self.assertEqual(self.js.eval('added.length'),0)
        self.js.eval("elements['#sentenceAutoAdd'].checked=true;elements['#sentenceAutoAdd'].change();elements['#sentenceAutoAdd'].change();")
        self.assertEqual(self.js.eval('JSON.stringify(added)'), '["HELLO"]')
        self.assertEqual(self.js.eval('spoken.length'),0)
    def test_hidden_word_match_is_rejected_without_relabeling(self):
        self.boot_studio()
        self.js.eval("for(let i=0;i<3;i++){record('HELLO',1);record('BYE',-1)}hiddenLabel='HELLO';record('',1,false);")
        self.assertTrue(self.js.eval("elements['#motionAccept'].disabled"))
        self.assertEqual(self.js.eval('added.length'),0)

    def test_nested_preview_keeps_older_words_priority(self):
        self.js.eval("const strict={maxDistance:.1,minRatio:1.3,minVotes:2,mirror:false};const prior={labels:['FAR'],parameters:strict,samples:Array.from({length:3},()=>({label:'FAR',sequence:sequence(3)}))};const expanded={labels:['FAR','NEW'],newLabels:['NEW'],parameters:strict,baselineExtra:prior,samples:prior.samples.concat(Array.from({length:3},()=>({label:'NEW',sequence:sequence(6)})))};")
        self.assertEqual(self.js.eval("recognizeExpandedMotion(sequence(3),examples,strict,expanded).label"),'FAR')
        self.assertEqual(self.js.eval("recognizeExpandedMotion(sequence(6),examples,strict,expanded).label"),'NEW')
    def test_cancel_and_no_hands_do_not_save(self):
        self.boot_studio()
        self.js.eval("elements['#motionTeach'].click();studio.cancel();")
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v3'])"))
        self.js.eval("elements['#motionTeach'].click();studio.frame({},6000);")
        self.assertFalse(self.js.eval("Boolean(stored['handspeak-motion-v3'])"))
        self.assertIn('Not enough', self.js.eval("elements['#motionHelp'].textContent"))
    def test_capture_status_and_slow_camera_diagnostics(self):
        self.boot_studio(pretrained=True)
        self.js.eval('studio.recognize();studio.frame({},1000);')
        self.assertTrue(self.js.eval('studio.isCapturing()'))
        self.assertIn('Get ready',self.js.eval("elements['#motionCaptureStatus'].textContent"))
        self.js.eval('for(let i=0;i<6;i++)studio.frame({},1500+i*400);studio.frame({},6000);')
        self.assertFalse(self.js.eval('studio.isCapturing()'))
        self.assertIn('6/12',self.js.eval("elements['#motionCaptureStatus'].textContent"))
        self.assertFalse(self.js.eval("elements['#wordCaptureButton'].disabled"))
    def test_eleven_frames_get_bounded_extension(self):
        self.boot_studio(pretrained=True)
        self.js.eval('studio.recognize();for(let i=0;i<11;i++)studio.frame({},1500+i*220);timers[0]();')
        self.assertTrue(self.js.eval('studio.isCapturing()'))
        self.assertIn('11/12',self.js.eval("elements['#motionCaptureStatus'].textContent"))
        self.js.eval('studio.frame({},4200);')
        self.assertFalse(self.js.eval('studio.isCapturing()'))
        self.assertIn('hand tracking',self.js.eval("elements['#motionCaptureStatus'].textContent"))
    def test_stalled_stream_times_out_and_cancel_discards_extension(self):
        self.boot_studio(pretrained=True)
        self.js.eval('studio.recognize();timers[0]();timers[1]();')
        self.assertFalse(self.js.eval('studio.isCapturing()'))
        self.assertIn('0/12',self.js.eval("elements['#motionCaptureStatus'].textContent"))
        self.js.eval('studio.recognize();timers[2]();studio.cancel();timers[3]();')
        self.assertFalse(self.js.eval('studio.isCapturing()'))
        self.assertIn('canceled',self.js.eval("elements['#motionCaptureStatus'].textContent"))
    def test_automatic_motion_pause_cooldown_and_reset(self):
        self.js.eval("""
          const auto=createAutomaticMotion();let clips=[];
          function feed(t,x){const hand=Array.from({length:21},(_,i)=>({x:x+i*.006,y:.4,z:0}));const result=auto.push([hand,null],t);if(result)clips.push(result);}
          for(let t=0;t<1000;t+=100)feed(t,.3);
        """)
        self.assertEqual(self.js.eval('clips.length'),0)
        self.js.eval('for(let t=1000;t<2200;t+=100)feed(t,.3+(t-1000)*.0002);for(let t=2200;t<4000;t+=100)feed(t,.52);')
        self.assertEqual(self.js.eval('clips.length'),1)
        self.assertGreaterEqual(self.js.eval('clips[0].frames.length'),12)
        self.js.eval('for(let t=4000;t<5200;t+=100)feed(t,.52-(t-4000)*.0002);for(let t=5200;t<6500;t+=100)feed(t,.3);')
        self.assertEqual(self.js.eval('clips.length'),2)
        self.js.eval('feed(6500,.5);auto.reset();')
        self.assertFalse(self.js.eval('auto.isActive()'))
    def test_automatic_continuous_motion_does_not_repeat_and_gaps_reset(self):
        self.js.eval("""
          const auto=createAutomaticMotion();let count=0;
          for(let t=0;t<12000;t+=100){const h=Array.from({length:21},(_,i)=>({x:.4+i*.006+Math.sin(t/150)*.1,y:.4,z:0}));if(auto.push([h,null],t))count++;}
        """)
        self.assertEqual(self.js.eval('count'),1)
        self.js.eval('auto.push([null,null],15000);')
        self.assertFalse(self.js.eval('auto.isActive()'))
    def test_optional_fast_capture_retains_short_visible_sign(self):
        result=json.loads(self.js.eval('''JSON.stringify([80,30].map(sampleIntervalMs=>{
          const a=createAutomaticMotion({sampleIntervalMs});let clips=[];
          for(let t=0;t<2200;t+=32){
            const h=t>=512&&t<960?Array.from({length:21},(_,i)=>({x:.2+i*.006+(t-512)*.0002,y:.4,z:0})):null;
            const clip=a.push([h,null],t,1);if(clip)clips.push(clip);
          }
          return clips.map(c=>({tracked:c.frames.filter(f=>f.some(Boolean)).length,valid:encodeMotion(c.frames,1)!==null}));
        }))'''))
        self.assertEqual(len(result[0]),1)
        self.assertFalse(result[0][0]['valid'])
        self.assertEqual(len(result[1]),1)
        self.assertTrue(result[1][0]['valid'])
        self.assertGreaterEqual(result[1][0]['tracked'],8)
    def test_automatic_studio_requires_no_record_button(self):
        self.boot_studio(pretrained=True)
        self.js.eval("""
          elements['#automaticWords'].checked=true;
          for(let t=0;t<3000;t+=100){
            const x=.3+Math.min(t,1500)*.0002;
            const hand=Array.from({length:21},(_,i)=>({x:x+i*.006,y:.4,z:0}));
            studio.frame({landmarks:[hand],handedness:[[{categoryName:'Left'}]]},t);
          }
        """)
        self.assertIn(self.js.eval("elements['#motionHelp'].textContent").split('.')[0],['Hands captured, but no word passed the matching checks','Possible match: “FORWARD”','Possible match: “BACK”'])
        self.assertEqual(self.js.eval('added.length'),0)
        self.assertEqual(self.js.eval('timers.length'),0)
if __name__=='__main__':unittest.main()
