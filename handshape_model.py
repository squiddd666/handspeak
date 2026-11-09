"""Small temporal model for full local handshape and body-relative wrists."""
import numpy as np
import torch
from torch import nn
from handshape_features import CHANNELS, VERSION, mirror


class TemporalHandshape(nn.Module):
    def __init__(self, classes, width=160):
        super().__init__()
        self.input = nn.Sequential(nn.Conv1d(CHANNELS, width, 1), nn.BatchNorm1d(width), nn.GELU())
        self.blocks = nn.ModuleList([nn.Sequential(
            nn.Conv1d(width, width, 3, padding=d, dilation=d), nn.BatchNorm1d(width),
            nn.GELU(), nn.Dropout(.2), nn.Conv1d(width, width, 1), nn.BatchNorm1d(width)
        ) for d in (1, 2, 4)])
        self.output = nn.Sequential(nn.Dropout(.4), nn.Linear(width * 6, classes))

    def forward(self, x):
        x = self.input(x)
        for block in self.blocks:
            x = torch.nn.functional.gelu(x + block(x))
        pooled = torch.cat([x.mean(-1), x.amax(-1),
                            torch.nn.functional.adaptive_avg_pool1d(x, 4).flatten(1)], 1)
        return self.output(pooled)


def load(path):
    blob = torch.load(path, map_location="cpu", weights_only=False)
    if blob.get("featureVersion") != VERSION or blob.get("architecture") != "temporal-handshape-v1":
        raise ValueError("Unknown handshape model contract")
    model = TemporalHandshape(len(blob["labels"]), blob.get("width", 160)).eval()
    model.load_state_dict(blob["state_dict"])
    return model, list(blob["labels"]), blob


def predict(model, tensors, batch=64):
    result = []
    with torch.inference_mode():
        for start in range(0, len(tensors), batch):
            values = tensors[start:start + batch]
            x = torch.from_numpy(np.stack(values + [mirror(v) for v in values]))
            p = model(x).softmax(1)
            result.append(((p[:len(values)] + p[len(values):]) / 2).numpy())
    return np.concatenate(result) if result else np.empty((0, model.output[-1].out_features), np.float32)
