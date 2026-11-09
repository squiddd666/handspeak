import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from scripts.report_motion_repair_v6 import compare, verify_retained_runtime


def report():
    return dict(activeModelSha256={'body':'frozen'},activeAuxiliaryModelSha256={'body':'aux'},calibrationSha256='calibration',
                isolation=dict(host='127.0.0.1',realCameraCalls=0,microphoneCalls=0),
                attempts=[dict(id=str(i),label=f'WORD {i}',clip=f'{i}.mp4',clipSha256=str(i),family='beginner',
                               vocabulary=None,rate=1,stage='baseline 1×',finishedAt='done',predicted=f'WORD {i}',correct=True) for i in range(28)])


class V6ReportTests(unittest.TestCase):
    def reports(self):
        return dict(baseline=report(),padding=report(),paddingParity=report())

    def test_separate_trials_keep_every_wrong_and_no_match(self):
        trials=self.reports()
        trials['padding']['attempts'][0].update(predicted='WRONG',correct=False)
        trials['paddingParity']['attempts'][1].update(predicted=None,correct=False)
        result=compare(trials)
        self.assertEqual(result['trials']['baseline']['matched'],28)
        self.assertEqual(result['trials']['padding']['incorrect'],1)
        self.assertEqual(result['trials']['paddingParity']['noMatch'],1)
        self.assertEqual(result['transitions']['padding']['regressions'],['WORD 0'])

    def test_duplicate_baseline_is_not_a_full_trial(self):
        trials=self.reports()
        for r in trials.values():r['attempts'][1]=copy.deepcopy(r['attempts'][0])
        with self.assertRaisesRegex(ValueError,'distinct'):compare(trials)

    def test_missing_reference_and_identity_change_are_rejected(self):
        for change in (dict(clipSha256='new'),dict(family='capstone'),dict(vocabulary='new'),dict(rate=.5),dict(finishedAt=None)):
            trials=self.reports();trials['padding']['attempts'][0].update(change)
            with self.assertRaises(ValueError):compare(trials)
        trials=self.reports();trials['padding']['attempts'].pop()
        with self.assertRaises(ValueError):compare(trials)

    def test_changed_weights_auxiliary_and_calibration_are_rejected(self):
        for key in ('activeModelSha256','activeAuxiliaryModelSha256','calibrationSha256'):
            trials=self.reports();trials['padding'][key]='changed'
            with self.assertRaisesRegex(ValueError,'model weights'):compare(trials)

    def test_false_correctness_physical_camera_and_raw_coordinates_are_rejected(self):
        for mutate in (lambda r:r['attempts'][0].update(predicted='WRONG'),
                       lambda r:r['isolation'].update(realCameraCalls=1),
                       lambda r:r['isolation'].update(host='outside'),
                       lambda r:r['attempts'][0].update(landmarks=[])):
            trials=self.reports();mutate(trials['padding'])
            with self.assertRaises(ValueError):compare(trials)

    def test_installed_runtime_is_checked_instead_of_assuming_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'index.html').write_bytes(b'index');(root/'app.js').write_bytes(b'retained')
            r=dict(indexSha256=hashlib.sha256(b'index').hexdigest(),runtimeSha256={'app.js':hashlib.sha256(b'retained').hexdigest()})
            self.assertIn('app.js',verify_retained_runtime(r,root))
            (root/'app.js').write_bytes(b'experiment')
            with self.assertRaisesRegex(ValueError,'runtime differs'):verify_retained_runtime(r,root)


if __name__=='__main__':unittest.main()
