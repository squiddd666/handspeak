import io
import unittest
import numpy as np
import torch
from train_motion_residual import MotionNet, augmented_batch, masked_feature_noise, class_weights, batch


class MotionResidualTest(unittest.TestCase):
    def test_target_weight_keeps_rejection_classes_in_loss(self):
        y = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])
        weights = class_weights(y, 4, 2, 2.)
        self.assertTrue((weights > 0).all())
        self.assertAlmostEqual(float(weights[0] / weights[2]), 2.)
        for invalid in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                class_weights(y, 4, 2, invalid)

    def test_masked_augmentation_does_not_invent_absent_landmarks(self):
        for channels in (153, 175):
            x = torch.zeros(2, channels, 32)
            self.assertTrue(torch.equal(augmented_batch(x, masked=True), x))

    def test_masked_noise_preserves_metadata_and_wrist_origin(self):
        x = torch.zeros(2, 175, 32)
        x[:, 0] = 1
        x[:, 68] = 1
        x[:, 138] = 1
        result = masked_feature_noise(x)
        self.assertTrue(torch.equal(result[:, :4], x[:, :4]))
        self.assertTrue(torch.equal(result[:, 68:139], x[:, 68:139]))
        self.assertTrue(torch.equal(result[:, 141:153], x[:, 141:153]))
        self.assertTrue(torch.equal(result[:, 164:], x[:, 164:]))
        self.assertGreater(result[:, 4:68].abs().sum(), 0)
        self.assertGreater(result[:, 139:141].abs().sum(), 0)
        self.assertTrue((result[:, 163] >= 0).all())

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
