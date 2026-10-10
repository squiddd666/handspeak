"""Development augmentation for distance/letterboxing; never adds tracked frames."""
import copy
import math

def scaled(row,factor):
    if not math.isfinite(factor) or factor<=0:raise ValueError('Scale must be positive and finite')
    if any(p is not None for p in row.get('body',[])):raise ValueError('Framing augmentation requires hands-only rows')
    result=copy.deepcopy(row)
    for frame in result['rawFrames']:
        for hand in frame:
            if hand:
                for point in hand:
                    point.update(x=.5+(point['x']-.5)*factor,y=.5+(point['y']-.5)*factor,z=point['z']*factor)
    result['augmentationScale']=factor
    return result
