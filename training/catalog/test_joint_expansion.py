import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

import expand_joint_data as expansion
import popsign_range


class JointExpansionTests(unittest.TestCase):
    def test_range_transport_reuses_connection_and_rejects_wrong_range(self):
        url = 'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/hot.tar'
        response = Mock(status=206)
        response.getheader.return_value = 'bytes 0-3/100'
        response.read.return_value = b'data'
        connection = Mock()
        connection.getresponse.return_value = response
        popsign_range.LOCAL.connection = None
        try:
            with patch.object(popsign_range.http.client, 'HTTPSConnection', return_value=connection) as factory:
                self.assertEqual(popsign_range.request(url, 0, 4), b'data')
                self.assertEqual(popsign_range.request(url, 0, 4), b'data')
                factory.assert_called_once()
                response.getheader.return_value = 'bytes 4-7/100'
                with patch.object(popsign_range.time, 'sleep'):
                    with self.assertRaises(ValueError):
                        popsign_range.request(url, 0, 4)
                with self.assertRaises(ValueError):
                    popsign_range.request(url.replace('/train/', '/test/'), 0, 4)
        finally:
            popsign_range.LOCAL.connection = None

    def test_reuses_gloss_mapping_excludes_existing_and_caps_signers(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            for signer in ('1001', '1002', '1003'):
                for i in range(3):
                    member = tarfile.TarInfo(f'owie/4a.{signer}-{i}.mp4')
                    member.size = 1
                    stream.addfile(member, io.BytesIO(b'x'))
        payload = archive.getvalue()
        url = 'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/owie.tar'
        base = [dict(label='PAIN', split='train', source=url, member='owie/4a.1001-0.mp4', participant='1001')]
        requests = []

        def request(source, start, size):
            requests.append(source)
            return payload[start:start+size]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'selection').mkdir()
            with patch.object(expansion.expansion.requests, 'request', side_effect=request):
                rows = expansion.select('PAIN', base, root, 5, {'2001'})
                self.assertEqual(len(rows), 4)
                self.assertEqual({r['source'] for r in rows}, {url})
                self.assertEqual(sum(r['participant'] == '1001' for r in rows), 1)
                self.assertEqual(sum(r['participant'] == '1002' for r in rows), 2)
                self.assertNotIn(base[0]['member'], {r['member'] for r in rows})
                count = len(requests)
                self.assertEqual(rows, expansion.select('PAIN', base, root, 5, {'2001'}))
                self.assertEqual(len(requests), count)

    def test_no_download_if_target_already_met_or_source_is_not_training(self):
        url = 'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/callonphone.tar'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'selection').mkdir()
            base = [dict(label='CALL', split='train', source=url, member='old.mp4', participant='1')]
            with patch.object(expansion.expansion.requests, 'request') as request:
                self.assertEqual(expansion.select('CALL', base, root, 1, set()), [])
                request.assert_not_called()
                with self.assertRaises(ValueError):
                    expansion.select('CALL', [dict(base[0], source=url.replace('/train/', '/test/'))], root, 1, set())

    def test_heldout_signer_in_training_archive_is_rejected(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            member = tarfile.TarInfo('hot/4a.2001-0.mp4')
            member.size = 1
            stream.addfile(member, io.BytesIO(b'x'))
        payload = archive.getvalue()
        base = [dict(label='HOT', split='train',
            source='https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/hot.tar',
            member='old.mp4', participant='1')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'selection').mkdir()
            with patch.object(expansion.expansion.requests, 'request', side_effect=lambda u, o, n: payload[o:o+n]):
                with self.assertRaises(ValueError):
                    expansion.select('HOT', base, root, 2, {'2001'})


if __name__ == '__main__':
    unittest.main()
