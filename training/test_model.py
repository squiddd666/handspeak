"""Run: python -m unittest discover -s training -v (requires quickjs)."""
import json
from pathlib import Path
import unittest

import numpy as np
import quickjs
from train_asl import normalize

ROOT = Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.js = quickjs.Context()
        self.js.eval((ROOT/'gesture-model.js').read_text().replace('export ', ''))
        self.model = json.loads((ROOT/'models/asl-knn.json').read_text())
        self.js.eval('const model = '+json.dumps(self.model)+';')

    def test_export_is_valid(self):
        self.assertTrue(self.js.eval('model.samples.every(s=>validSample(s, model.labels))'))
        self.assertEqual(set(self.model['labels']), set('ABILVWY'))
        self.assertFalse(self.js.eval("validSample({label:'A',features:[1]}, ['A'])"))

    def test_normalization_matches_training(self):
        points = np.random.default_rng(9).random((21, 3))
        objects = [dict(zip(['x', 'y', 'z'], p)) for p in points]
        actual = json.loads(self.js.eval('JSON.stringify(normalizeLandmarks('+json.dumps(objects)+'))'))
        np.testing.assert_allclose(actual, normalize(points), atol=0.000001)

    def test_held_out_predictions_match_python(self):
        fixtures = json.loads((ROOT/'models/asl-test-fixture.json').read_text())
        for row in fixtures:
            result = self.js.eval('(classifyFeatures('+json.dumps(row['features'])+',model.samples)||{}).letter || null')
            self.assertEqual(result, row['expected'], row['label'])
            mirrored = [(-v if i%3==0 else v) for i,v in enumerate(row['features'])]
            mirror_result = self.js.eval('(classifyFeatures('+json.dumps(mirrored)+',model.samples)||{}).letter || null')
            self.assertEqual(mirror_result, row['expected'])
        self.assertIsNone(self.js.eval('classifyFeatures(Array(63).fill(0),[])'))

    def boot_app(self, failure=False):
        self.js.eval('''
          const elements = {};
          const createInterpreter=()=>({});
          const createResearchWords=()=>({active:()=>false,cancel(){},disable(){},isCapturing:()=>false});
          const createVocabularyLibrary=()=>({showCameraAccuracy(){}});
          const createCapstoneRecognition=()=>({frame(){},cancel(){},isCapturing:()=>false});
          const CustomEvent=function(name,options){this.type=name;this.detail=options?.detail;}; const document = {dispatchEvent(){},querySelectorAll:()=>[],querySelector: key => elements[key] ||= {
            style:{}, listeners:{}, classList:{add(){}, remove(){}, toggle(){}},
            addEventListener(name, fn){this.listeners[name]=fn}, getContext(){return {clearRect(){}}}
          }};
          const window = {addEventListener(){}};
          const localStorage = {getItem(){return null},setItem(){},removeItem(){}};
          const console = {warn(){}}; const createExperienceUI=()=>{}; const loadVocabularySettings=async()=>({}); const isWordEnabled=()=>true;
          function setTimeout(){} function clearTimeout(){} function clearInterval(){} function cancelAnimationFrame(){}
        ''')
        self.js.eval('const fetch = async path => '+(
            "({ok:false,json:async()=>({})});" if failure else
            "path.includes('asl-knn') ? ({ok:true,json:async()=>model}) : ({ok:false,json:async()=>({})});"
        ))
        for name in ['camera-performance.js','temporal-camera.js','temporal-word-model.js','sentence-builder.js','motion-model.js','automatic-motion.js','expanded-motion.js','motion-studio.js','face-tracker.js']:
            code='\n'.join(line for line in (ROOT/name).read_text().splitlines() if not line.startswith('import '))
            self.js.eval(code.replace('export ', ''))
        app = '\n'.join(line for line in (ROOT/'app.js').read_text().splitlines() if not line.startswith('import '))
        self.js.eval(app)
        while self.js.execute_pending_job():
            pass

    def test_recognition_feedback_is_qualitative_and_resets(self):
        self.boot_app()
        self.js.eval("setLive('A', .87)")
        self.assertIn('Possible match', self.js.eval("liveConfidence.textContent"))
        self.assertNotIn('%', self.js.eval("liveConfidence.textContent"))
        self.js.eval("setLive('')")
        self.assertIn('No reliable match', self.js.eval("elements['#recognitionFeedback'].textContent"))
        self.js.eval("committed='A';setLive('A')")
        self.assertIn('recognized', self.js.eval("elements['#recognitionFeedback'].textContent"))
        self.js.eval("setRecognitionMode('words')")
        self.assertIn('Camera off', self.js.eval("elements['#recognitionFeedback'].textContent"))

    def test_start_signing_does_not_stop_active_camera(self):
        self.boot_app()
        self.js.eval("running=true;$('#workspace').scrollIntoView=()=>{};elements['#startSigning'].listeners.click()")
        self.assertTrue(self.js.eval('running'))

    def test_auto_load_and_personal_reset(self):
        self.boot_app()
        self.assertEqual(self.js.eval('baseSamples.length'), len(self.model['samples']))
        self.assertIn('7 pretrained letters', self.js.eval("elements['#aiModelStatus'].textContent"))
        self.js.eval("aiSamples.push(model.samples[0]); elements['#resetModelButton'].listeners.click();")
        self.assertEqual(self.js.eval('aiSamples.length'), 0)
        self.assertEqual(self.js.eval('baseSamples.length'), len(self.model['samples']))

    def test_download_failure_reports_unavailable(self):
        self.boot_app(failure=True)
        self.assertEqual(self.js.eval('baseSamples.length'), 0)
        self.assertIn('unavailable', self.js.eval("elements['#aiModelStatus'].textContent"))

    def test_unfamiliar_and_ambiguous_poses_are_rejected(self):
        self.assertIsNone(self.js.eval('classifyFeatures(Array(63).fill(100),model.samples)'))
        self.assertIsNone(self.js.eval('classifyFeatures([NaN],model.samples)'))
        self.js.eval("const ambiguous=Array.from({length:20},(_,i)=>({label:i<10?'A':'B',features:Array(63).fill(0)}));")
        self.assertIsNone(self.js.eval('classifyFeatures(Array(63).fill(0),ambiguous)'))

    def test_training_locks_label_and_saves_complete_batch(self):
        self.boot_app()
        self.js.eval("""
          running=true; elements['#trainingLabel'].value='A';
          elements['#captureSamplesButton'].listeners.click();
          elements['#trainingLabel'].value='B';
          const sample=model.samples[0].features;
          const points=Array.from({length:21},(_,i)=>({x:.5+sample[i*3]*.05,y:.5+sample[i*3+1]*.05,z:sample[i*3+2]*.05}));
          captureTrainingSample(points,200);
        """)
        self.assertEqual(self.js.eval('aiSamples.length'), 0)
        self.assertTrue(self.js.eval("elements['#trainingLabel'].disabled"))
        self.js.eval('for(let i=2;i<=30;i++)captureTrainingSample(points,i*200);')
        self.assertEqual(self.js.eval('aiSamples.length'), 30)
        self.assertTrue(self.js.eval("aiSamples.every(s=>s.label==='A')"))
        self.assertFalse(self.js.eval('trainingActive'))

    def test_camera_stop_discards_partial_capture_and_stale_candidate(self):
        self.boot_app()
        self.js.eval("""
          running=true; elements['#trainingLabel'].value='A';
          elements['#captureSamplesButton'].listeners.click();
          pendingSamples.push(model.samples[0]);candidate='A';candidateSince=100;committed='A';
          stopCamera();
        """)
        self.assertEqual(self.js.eval('pendingSamples.length'), 0)
        self.assertEqual(self.js.eval('aiSamples.length'), 0)
        self.assertEqual(self.js.eval('candidate'), '')
        self.assertFalse(self.js.eval('trainingActive'))

    def test_cancelled_camera_start_cannot_stop_a_new_attempt(self):
        self.boot_app()
        self.js.eval('''
          const navigator={mediaDevices:{getUserMedia(){}}};
          let rejectOld;
          createTemporalCamera=()=>({ready:new Promise((resolve,reject)=>{rejectOld=reject}),close(){}});
          motionStudio.usesTemporalModel=()=>true;recognitionMode='words';
          startCamera();
        ''')
        while self.js.execute_pending_job():pass
        self.js.eval('''
          stopCamera();
          cameraAttempt++;cameraStarting=true;cameraButton.disabled=true;
          rejectOld(Error('Old worker stopped'));
        ''')
        while self.js.execute_pending_job():pass
        self.assertTrue(self.js.eval('cameraStarting'))
        self.assertTrue(self.js.eval('cameraButton.disabled'))


    def test_camera_processes_new_frames_only_and_never_types_during_training(self):
        self.boot_app()
        self.js.eval("""
          const sample=model.samples[0].features;
          const points=Array.from({length:21},(_,i)=>({x:.5+sample[i*3]*.05,y:.5+sample[i*3+1]*.05,z:sample[i*3+2]*.05}));
          const performance={now:()=>1000};
          function requestAnimationFrame(){}
          let calls=0,stabilized=0;
          handLandmarker={detectForVideo(){calls++;return {landmarks:[points]}}};
          drawHand=()=>{};stabilize=()=>{stabilized++};
          video.readyState=2;video.currentTime=1;video.videoWidth=640;video.videoHeight=480;
          running=true; elements['#trainingLabel'].value='A';
          elements['#captureSamplesButton'].listeners.click();
          detect();detect();
        """)
        self.assertEqual(self.js.eval('calls'), 1)
        self.assertEqual(self.js.eval('stabilized'), 0)
        self.assertEqual(self.js.eval('pendingSamples.length'), 1)
        self.js.eval('endTraining();video.currentTime=2;detect();')
        self.assertEqual(self.js.eval('stabilized'), 1)

    def test_hand_error_does_not_stop_face_loop(self):
        self.boot_app()
        self.js.eval('''
          const performance={now:()=>1000};let faceFrames=0,scheduled=0;
          function requestAnimationFrame(){scheduled++}
          faceTracker.draw=()=>{faceFrames++};
          handLandmarker={detectForVideo(){throw Error('GPU lost')},close(){}};
          video.readyState=2;video.currentTime=1;video.videoWidth=640;video.videoHeight=480;running=true;
          detect();video.currentTime=2;detect();
        ''')
        self.assertEqual(self.js.eval('faceFrames'),2)
        self.assertEqual(self.js.eval('scheduled'),2)
        self.assertIsNone(self.js.eval('handLandmarker'))

    def test_gpu_runtime_failure_retries_cpu_and_resumes_detection(self):
        self.boot_app()
        self.js.eval('''
          const performance={now:()=>1000};function requestAnimationFrame(){}
          let resolveCPU,closed=0,cpuCalls=0;
          handVision={HandLandmarker:{createFromOptions(files,options){if(options.baseOptions.delegate!=='CPU')throw Error('Expected CPU');return new Promise(resolve=>{resolveCPU=resolve})}}};
          handDelegate='GPU';handLandmarker={detectForVideo(){throw Error('Android GPU context lost')},close(){closed++}};
          video.readyState=2;video.currentTime=1;video.videoWidth=640;video.videoHeight=480;running=true;
          detect();
        ''')
        self.assertEqual(self.js.eval('cameraDiagnostic.trackerState'),'recovering')
        self.assertEqual(self.js.eval('closed'),1)
        self.js.eval("resolveCPU({detectForVideo(){cpuCalls++;return {landmarks:[]}},close(){closed++}})")
        while self.js.execute_pending_job():pass
        self.assertEqual(self.js.eval('handDelegate'),'CPU')
        self.js.eval('video.currentTime=2;detect()')
        self.assertEqual(self.js.eval('cpuCalls'),1)
        self.assertEqual(self.js.eval('cameraDiagnostic.trackerState'),'ready')

    def test_stopped_camera_discards_late_cpu_recovery(self):
        self.boot_app()
        self.js.eval('''
          let resolveCPU,closed=0;
          handVision={HandLandmarker:{createFromOptions(){return new Promise(resolve=>{resolveCPU=resolve})}}};
          handDelegate='GPU';handLandmarker={close(){}};running=true;
          handTrackerFailed(Error('GPU context lost'));stopCamera();
          resolveCPU({close(){closed++}});
        ''')
        while self.js.execute_pending_job():pass
        self.assertIsNone(self.js.eval('handLandmarker'))
        self.assertEqual(self.js.eval('closed'),1)

    def test_camera_restart_retries_face_model(self):
        self.boot_app()
        self.js.eval('let faceLoads=0;faceTracker.load=()=>{faceLoads++};handLandmarker={};loadRecognizer();')
        while self.js.execute_pending_job():pass
        self.assertEqual(self.js.eval('faceLoads'),1)
    def test_camera_word_button_selects_word_mode(self):
        self.boot_app()
        self.js.eval("let started=0;running=true;motionStudio.recognize=()=>{started++};motionStudio.isRecording=()=>true;elements['#wordCaptureButton'].listeners.click();")
        while self.js.execute_pending_job():pass
        self.assertEqual(self.js.eval('recognitionMode'),'words')
        self.assertEqual(self.js.eval('started'),1)
        self.assertTrue(self.js.eval("elements['#wordCaptureButton'].disabled"))



if __name__ == '__main__':
    unittest.main()
