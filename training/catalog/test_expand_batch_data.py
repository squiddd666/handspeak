import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import expand_batch_data as expansion


class DataExpansionTests(unittest.TestCase):
    def test_additional_manifest_rejects_test_split_and_validation_signer(self):
        base = [dict(split='val', participant='b')]
        good = dict(split='train', participant='a', source='https://example/game/train/hot.tar')
        expansion.validate_training_rows([good], base)
        for bad in [dict(good, split='test'), dict(good, participant='b'),
                    dict(good, source='https://example/game/test/hot.tar')]:
            with self.assertRaises(ValueError):
                expansion.validate_training_rows([bad], base)

    def test_selection_only_requests_train_and_limits_each_signer(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as archive:
            for signer in ('1001', '1002'):
                for repetition in range(4):
                    item = tarfile.TarInfo(f'hot/gtsignstudy4a.{signer}-hot-{repetition}.mp4')
                    item.size = 1
                    archive.addfile(item, io.BytesIO(b'x'))
        payload = buffer.getvalue()
        requests = []

        def get(url, start, size):
            requests.append(url)
            return payload[start:start + size]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'selection').mkdir()
            with patch.object(expansion, 'ROOT', root), patch.object(
                    expansion.requests, 'request', side_effect=get):
                rows = expansion.select('HOT')
                self.assertEqual(len(rows), 4)
                self.assertEqual({r['split'] for r in rows}, {'train'})
                self.assertTrue(all('/game/train/hot.tar' in url for url in requests))
                self.assertEqual(sum(r['participant'] == '1001' for r in rows), 2)
                count = len(requests)
                self.assertEqual(expansion.select('HOT'), rows)
                self.assertEqual(len(requests), count)
                expansion.select('CALL')
                self.assertTrue(all('/game/train/callonphone.tar' in url
                                    for url in requests[count:]))

    def test_incomplete_existing_download_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.mp4'
            path.write_bytes(b'x')
            with self.assertRaises(ValueError):
                expansion.download(dict(file=str(path), size=2))


if __name__ == '__main__':
    unittest.main()
