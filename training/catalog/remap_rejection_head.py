"""Split a learned generic rejection logit while retaining its probability mass."""
import math
import torch

def remap(old_state,new_state,old_labels,new_labels):
    if len(set(old_labels))!=len(old_labels) or len(set(new_labels))!=len(new_labels):raise ValueError('Duplicate class names')
    added=[label for label in new_labels if label not in old_labels]
    if [label for label in old_labels if label not in new_labels]!=['OTHER MOVEMENT'] or not added or not all(label.startswith('MOVEMENT: ') for label in added):raise ValueError('Only ordinary rejection may be split')
    result={key:value.clone() for key,value in new_state.items()}
    for key,value in old_state.items():
        if not key.startswith('head.'):result[key]=value.clone()
    old_other=old_labels.index('OTHER MOVEMENT')
    for i,label in enumerate(new_labels):
        source=old_labels.index(label) if label in old_labels else old_other
        result['head.1.weight'][i]=old_state['head.1.weight'][source]
        result['head.1.bias'][i]=old_state['head.1.bias'][source]-(math.log(len(added)) if label in added else 0)
    return result
