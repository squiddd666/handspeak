import unittest
import tarfile
from scripts.prepare_online_motion_audit import recording_key, safe_member, validate_range, select_archive, records, Fetcher, LABELS, NEGATIVES, MISSING_TARGETS
from scripts.prepare_targeted_data_v4 import MANUAL


class OnlineMotionAuditTests(unittest.TestCase):
    def test_legacy_key_equivalence(self):
        a = recording_key('hello/4a.8035-hello-2023_01_26_16_19_25.658-0.mp4')
        self.assertEqual(a, recording_key('hello/gtsignstudy4a.8035-hello-2023_01_26_16_19_25.658-0.mp4'))
        self.assertIsNone(recording_key('111c-hello-2023_01_26_16_19_25.658-0.mp4'))

    def test_unsafe_or_mislabeled_members_rejected(self):
        for member in ('/hello/4a.8035-hello-x.mp4', '../hello/4a.8035-hello-x.mp4',
                       'hello/../4a.8035-hello-x.mp4', 'hello\\4a.8035-hello-x.mp4',
                       'hello/4a.8035-no-x.mp4', 'no/4a.8035-no-x.mp4'):
            with self.assertRaises(ValueError):
                safe_member(member, 'hello')

    def test_exact_partial_response_required(self):
        self.assertEqual(validate_range(206, {'Content-Range': 'bytes 4-7/20'}, b'1234', 4, 7), 20)
        for status, content_range, data in ((200, 'bytes 4-7/20', b'1234'), (206, 'bytes 0-3/20', b'1234'),
                                            (206, 'bytes 4-7/20', b'123'), (206, 'bytes 4-7/7', b'1234')):
            with self.assertRaises(ValueError):
                validate_range(status, {'Content-Range': content_range}, data, 4, 7)

    def test_credentials_or_other_hosts_never_fetched(self):
        fetcher = Fetcher()
        for url in ('http://signdata.cc.gatech.edu/data/x.tar', 'https://evil.invalid/x.tar',
                    'https://user:pass@signdata.cc.gatech.edu/data/x.tar',
                    'https://signdata.cc.gatech.edu/res/downsampled/x.mp4',
                    'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/no.tar'):
            with self.assertRaises(ValueError):
                fetcher.range(url, 0, 511)

    def test_metadata_selection_excludes_known_recordings_and_fitting_signers(self):
        names = ['hello/4a.8001-hello-a.mp4', 'hello/4a.8031-hello-a.mp4',
                 'hello/4a.8031-hello-b.mp4', 'hello/4a.8031-hello-c.mp4',
                 'hello/4a.8032-hello-a.mp4']
        blocks = []
        for name in names:
            info = tarfile.TarInfo(name); info.size = 1
            blocks += [info.tobuf(), b'x' + bytes(511)]
        archive = b''.join(blocks) + bytes(1024)
        class Fake:
            def range(self, url, start, end):
                return archive[start:end+1], len(archive), 'frozen'
        source_map = {'test': {'orig_name': {str(i): n.split('/', 1)[1] for i, n in enumerate(names)}}}
        result = select_archive('hello', source_map, Fake(), {('8031', 'hello-a.mp4')}, {'8001'}, count=3)
        self.assertEqual([r['participant'] for r in result['selected']], ['8031', '8032'])
        self.assertTrue(result['incomplete'])
        self.assertEqual([r['reason'] for r in result['observed']], ['fitting-signer', 'known-recording', 'selected', 'signer-already-selected-for-word', 'selected'])

    def test_feature_arrays_not_provenance(self):
        found = list(records({'items': [{'member': 'yes.mp4'}], 'frames': [{'member': 'ignore.mp4'}]}))
        self.assertFalse(any(r.get('member') == 'ignore.mp4' for r in found))

    def test_candidate_coverage_and_negatives_not_silently_remapped(self):
        positives = {label for slug, label in LABELS.items() if slug not in NEGATIVES}
        negatives = {LABELS[slug] for slug in NEGATIVES}
        self.assertEqual(set(MANUAL) - positives, set(MISSING_TARGETS))
        self.assertFalse(negatives & set(MANUAL))
        self.assertNotIn('hurt', LABELS)
        self.assertNotIn('wantto', LABELS)
        self.assertNotIn('petsname', LABELS)

    def test_changing_archive_rejected(self):
        names = ['hello/4a.8031-hello-a.mp4', 'hello/4a.8032-hello-a.mp4']
        blocks = []
        for name in names:
            info = tarfile.TarInfo(name); info.size = 1
            blocks += [info.tobuf(), b'x' + bytes(511)]
        archive = b''.join(blocks) + bytes(1024)
        class Fake:
            def range(self, url, start, end):
                return archive[start:end+1], len(archive), 'v1' if start == 0 else 'v2'
        source_map = {'test': {'orig_name': {str(i): n.split('/', 1)[1] for i, n in enumerate(names)}}}
        with self.assertRaisesRegex(ValueError, 'Archive changed'):
            select_archive('hello', source_map, Fake(), set(), set())

    def test_fixed_metadata_offset_preserves_a_shortfall(self):
        names = ['hello/4a.8031-hello-a.mp4', 'hello/4a.8032-hello-a.mp4']
        blocks = []
        for name in names:
            info = tarfile.TarInfo(name); info.size = 1
            blocks += [info.tobuf(), b'x' + bytes(511)]
        archive = b''.join(blocks) + bytes(1024)
        class Fake:
            def range(self, url, start, end):
                return archive[start:end+1], len(archive), 'same'
        source_map = {'test': {'orig_name': {str(i): n.split('/', 1)[1] for i, n in enumerate(names)}}}
        result = select_archive('hello', source_map, Fake(), set(), set(), min_video_index=1)
        self.assertEqual([r['participant'] for r in result['selected']], ['8032'])
        self.assertEqual(result['observed'][0]['reason'], 'before-fixed-archive-offset')
        self.assertTrue(result['incomplete'])


if __name__ == '__main__':
    unittest.main()
