import io
import json
from pathlib import Path
import tempfile
import unittest

import torch
import train_expansion_batch as batch


class TemporalPhasesTests(unittest.TestCase):
    def test_ordered_regions_preserve_early_versus_late_activity(self):
        # Isolate the pooling/head behavior with identity-like positive filters.
        early = torch.zeros(1, 153, 32)
        early[:, 0, 3:5] = 1
        late = early.flip(-1)
        outputs = []
        for bins in (1, 4):
            net = batch.trainer.Net(1, num_classes=2, temporal_bins=bins).eval()
            with torch.no_grad():
                for param in net.parameters():
                    param.zero_()
                net.net[0].weight[0, 0, 2] = 1
                net.net[3].weight[0, 0, 1] = 1
                net.net[7].weight[0, 0] = 1
                outputs.append((net(early), net(late)))
        self.assertTrue(torch.equal(*outputs[0]))
        self.assertFalse(torch.equal(*outputs[1]))

    def test_expanded_checkpoint_roundtrip(self):
        net = batch.trainer.Net(16, num_classes=51, temporal_bins=4).eval()
        inputs = torch.randn(2, 153, 32)
        payload = io.BytesIO()
        torch.save(net.state_dict(), payload)
        payload.seek(0)
        reloaded = batch.trainer.Net(16, num_classes=51, temporal_bins=4).eval()
        reloaded.load_state_dict(torch.load(payload, weights_only=True))
        self.assertEqual(tuple(reloaded(inputs).shape), (2, 51))
        torch.testing.assert_close(net(inputs), reloaded(inputs))

    def test_architecture_frozen_and_invalid_bins_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'data.json'
            source.write_text(json.dumps([
                dict(label=label, split=split, participant=split, sha256=split+label,
                     rawFrames=[], sequence=[[1]])
                for split in ('train', 'val') for label in ('BOOK', 'OTHER')]))
            batch.prepare(source, root / 'out', labels=['BOOK'], temporal_bins=4)
            with self.assertRaises(ValueError):
                batch.prepare(source, root / 'out', labels=['BOOK'], temporal_bins=1)
            with self.assertRaises(ValueError):
                batch.trainer.Net(16, temporal_bins=0)


if __name__ == '__main__':
    unittest.main()
