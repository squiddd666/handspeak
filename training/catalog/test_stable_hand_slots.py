import copy
import unittest
from stable_hand_slots import stabilize


def hand(x):
    return [dict(x=x, y=.4, z=0) for _ in range(21)]


class StableSlotsTest(unittest.TestCase):
    def test_corrects_flicker_without_changing_coordinates_or_quality(self):
        row = dict(rawFrames=[[hand(.2), None], [None, hand(.21)], [hand(.22), None]],
                   imageAspect=1, sequence=None)
        original = copy.deepcopy(row)
        result = stabilize(row)
        self.assertEqual(row, original)
        self.assertEqual(result['stabilizedSlotFrames'], 1)
        self.assertEqual(result['rawFrames'][1], [row['rawFrames'][1][1], None])
        self.assertIsNone(result['sequence'])

    def test_missing_two_hand_and_distant_frames_break_tracks(self):
        for middle in ([None, None], [hand(.2), hand(.21)], [None, hand(.9)]):
            row = dict(rawFrames=[[hand(.2), None], middle, [None, hand(.21)]], imageAspect=1)
            self.assertEqual(stabilize(row)['rawFrames'], row['rawFrames'])

    def test_mirrored_tie_uses_mirrored_first_slot(self):
        row = dict(rawFrames=[[hand(.2), None], [None, hand(.21)]], imageAspect=1)
        mirrored = dict(row, rawFrames=[[None if h is None else [dict(p, x=1-p['x']) for p in h]
                                        for h in reversed(f)] for f in row['rawFrames']])
        a, b = stabilize(row), stabilize(mirrored)
        self.assertTrue(all(f[0] is not None for f in a['rawFrames']))
        self.assertTrue(all(f[1] is not None for f in b['rawFrames']))


if __name__ == '__main__':
    unittest.main()
