import io
import unittest
import numpy as np
import torch
from train_motion_residual import MotionNet, augmented_batch, batch


class MotionResidualTest(unittest.TestCase):
    def test_checkpoint_round_trip_and_batch_independence(self):
        torch.manual_seed(17)
        net = MotionNet(4, torch.zeros(153), torch.ones(153)).eval()
        x = torch.randn(3, 153, 32)
        with torch.no_grad():
            expected = net(x)
            self.assertTrue(torch.allclose(net(x[:1]), expected[:1], atol=1e-5))
        buffer = io.BytesIO()
        torch.save(net.state_dict(), buffer); buffer.seek(0)
        restored = MotionNet(4, torch.ones(153), torch.full((153,), 2.)).eval()
        restored.load_state_dict(torch.load(buffer, weights_only=True))
        with torch.no_grad():
            self.assertTrue(torch.equal(expected, restored(x)))

    def test_zero_motion_and_augmentation_are_finite(self):
        x = torch.zeros(2, 153, 32)
        net = MotionNet(4, torch.zeros(153), torch.full((153,), .1))
        logits = net(augmented_batch(x))
        self.assertTrue(torch.isfinite(logits).all())
        logits.sum().backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in net.parameters()))

    def test_rejection_winner_and_failed_tracking_never_fall_back(self):
        original = batch.trainer.LABELS
        try:
            batch.trainer.LABELS = ['ONE', 'TWO']
            rows = [dict(sequence=[1]), dict(sequence=None)]
            probs = np.array([[.35, .05, .6], [.95, .025, .025]])
            self.assertEqual(batch.trainer.outputs(rows, probs, .35, 0), [None, None])
        finally:
            batch.trainer.LABELS = original


if __name__ == '__main__':
    unittest.main()
