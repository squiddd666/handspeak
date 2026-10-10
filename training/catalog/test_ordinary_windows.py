import unittest
from ordinary_windows import window_rows

class WindowsTest(unittest.TestCase):
    def test_real_frames_and_original_identity_only(self):
        row=dict(sha256='source-hash',participant='person',split='train',rawFrames=[[None,None] for _ in range(61)],timestamps=list(range(0,12001,200)),sequence=[1])
        windows=window_rows(row)
        self.assertEqual(len(windows),4)
        self.assertEqual(len({w['exampleId'] for w in windows}),4)
        for w in windows:
            self.assertEqual(w['sha256'],row['sha256'])
            self.assertEqual(w['split'],'train')
            self.assertIsNone(w['sequence'])
            self.assertLessEqual(w['timestamps'][-1]-w['timestamps'][0],3000)
            self.assertEqual(len(w['rawFrames']),len(w['timestamps']))
            self.assertEqual(w['trackedFrames'],0)
    def test_bad_time_is_rejected(self):
        with self.assertRaises(ValueError):window_rows(dict(rawFrames=[[],[]],timestamps=[1,1]))
    def test_short_clip_not_duplicated(self):
        self.assertEqual(window_rows(dict(rawFrames=[[],[]],timestamps=[0,1000])),[])

if __name__=='__main__':unittest.main()
