import copy
import unittest
import json
import random
from pathlib import Path
import quickjs
from motion_window import align_window


def hand(x):
    return [dict(x=x, y=.3, z=0) for _ in range(21)]


class MotionWindowTest(unittest.TestCase):
    def row(self, frames):
        return dict(rawFrames=frames, body=list(range(len(frames))),
                    timestamps=list(range(len(frames))), sequence=None)

    def test_trim_and_gap_preserve_quality_and_original(self):
        row = self.row([[None, None], [hand(0), None], [None, None],
                        [hand(2), None], [None, None]])
        original = copy.deepcopy(row)
        out = align_window(row)
        self.assertEqual(row, original)
        self.assertEqual(out['body'], [1, 2, 3])
        self.assertEqual(out['rawFrames'][1][0][0]['x'], 1)
        self.assertIsNone(out['sequence'])
        self.assertEqual(out['timestamps'], [1, 2, 3])

    def test_disconnected_runs_not_joined(self):
        row = self.row([[hand(0), None]] * 8 + [[None, None]] * 4 + [[hand(1), None]] * 8)
        self.assertEqual(len(align_window(row)['rawFrames']), 20)

    def test_dominant_run_matches_encoder_rule(self):
        row = self.row([[hand(0), None]] + [[None, None]] * 4 + [[hand(1), None]] * 8)
        out = align_window(row)
        self.assertEqual(out['temporalWindow'], [5, 13])
        self.assertEqual(out['body'], list(range(5, 13)))

    def test_empty_frames_remain_empty(self):
        row = self.row([[None, None]] * 12)
        self.assertEqual(align_window(row), row)

    def test_windows_match_browser_encoder_before_normalization(self):
        context = quickjs.Context()
        source = (Path(__file__).resolve().parents[2] / 'motion-model.js').read_text()
        marker = 'const first=visible.flatMap(frame=>frame.filter(Boolean));'
        self.assertEqual(source.count(marker), 1)
        context.eval(source.replace('export ', '').replace(marker, 'return frames;\n' + marker))
        rng = random.Random(71)
        checked = 0
        for _ in range(40):
            frames = [[hand(rng.random()) if rng.random() > .3 else None,
                       hand(rng.random()) if rng.random() > .6 else None] for _ in range(30)]
            expected = json.loads(context.eval('JSON.stringify(encodeMotion(' + json.dumps(frames) + ',1))'))
            if expected is None:
                continue
            actual = align_window(self.row(frames))['rawFrames']
            self.assertEqual(actual, expected)
            checked += 1
        self.assertGreater(checked, 20)


if __name__ == '__main__':
    unittest.main()
