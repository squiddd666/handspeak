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
        self.js.eval((ROOT/'gesture-model.js').read_text().replace('export function', 'function'))
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
        self.assertIsNone(self.js.eval('classifyFeatures(Array(63).fill(0),[])'))

    def boot_app(self, failure=False):
        self.js.eval('''
          const elements = {};
          const document = {querySelector: key => elements[key] ||= {
            style:{}, listeners:{}, classList:{add(){}, remove(){}, toggle(){}},
            addEventListener(name, fn){this.listeners[name]=fn}, getContext(){return {}}
          }};
          const window = {addEventListener(){}};
          const localStorage = {getItem(){return null},setItem(){},removeItem(){}};
          const console = {warn(){}};
          function setTimeout(){} function clearTimeout(){}
        ''')
        self.js.eval('const fetch = async path => '+(
            "({ok:false,json:async()=>({})});" if failure else
            "path.includes('asl-knn') ? ({ok:true,json:async()=>model}) : ({ok:false,json:async()=>({})});"
        ))
        app = (ROOT/'app.js').read_text().split('\n', 1)[1]
        self.js.eval(app)
        while self.js.execute_pending_job():
            pass

    def test_auto_load_and_personal_reset(self):
        self.boot_app()
        self.assertEqual(self.js.eval('baseSamples.length'), len(self.model['samples']))
        self.assertIn('7 pretrained letters', self.js.eval("elements['#aiModelStatus'].textContent"))
        self.js.eval("aiSamples.push(model.samples[0]); elements['#resetModelButton'].listeners.click();")
        self.assertEqual(self.js.eval('aiSamples.length'), 0)
        self.assertEqual(self.js.eval('baseSamples.length'), len(self.model['samples']))

    def test_download_failure_keeps_rules_available(self):
        self.boot_app(failure=True)
        self.assertEqual(self.js.eval('baseSamples.length'), 0)
        self.assertIn('unavailable', self.js.eval("elements['#aiModelStatus'].textContent"))


if __name__ == '__main__':
    unittest.main()
