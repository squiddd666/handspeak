"""Retain fingertip/body position and hand/body scale lost by palm normalization."""
import numpy as np
from train_expansion_batch import trainer


def features(row):
    base = trainer.encoding.features(row)
    frames = row['rawFrames']; aspect = row['imageAspect']
    body = row.get('body', [None] * len(frames))
    wrists = [(h[0]['x'], h[0]['y'] * aspect) for f in frames for h in f if h]
    center = np.mean(wrists, axis=0) if wrists else np.zeros(2)
    vectors = []
    for frame, pose in zip(frames, body):
        good = bool(pose and min(pose[1]['visibility'], pose[2]['visibility']) > .5)
        origin = np.mean([[pose[i]['x'], pose[i]['y'] * aspect] for i in [1,2]], axis=0) if good else center
        scale = max(.08, np.hypot(pose[1]['x']-pose[2]['x'], (pose[1]['y']-pose[2]['y'])*aspect)) if good else .2
        vector = []
        for hand in frame:
            if hand is None:
                vector.extend([0.] * 11)
                continue
            for tip in (4,8,12,16,20):
                vector.extend([(hand[tip]['x']-origin[0])/scale, (hand[tip]['y']*aspect-origin[1])/scale])
            vector.append(np.hypot(hand[5]['x']-hand[17]['x'], (hand[5]['y']-hand[17]['y'])*aspect)/scale)
        vectors.append(vector)
    if not vectors:
        extra = np.zeros((22,32), np.float32)
    else:
        values = np.nan_to_num(np.clip(np.array(vectors), -10, 10))
        t = np.linspace(0,len(values)-1,32)
        extra = np.stack([np.interp(t,np.arange(len(values)),values[:,i]) for i in range(22)]).astype(np.float32)
    return np.concatenate([base,extra])
