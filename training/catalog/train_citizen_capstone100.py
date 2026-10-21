"""Fine-tune CAPSTONE_ASL on official ASL Citizen train/validation splits."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "third_party" / "capstone_asl"))
import pipeline

ROOT = Path("/opt/handspeak-training/capstone100-retrain")
LABELS = REPO / "third_party/capstone_asl/data/recognition_label_map_with_split_counts.csv"
PHASE = REPO / "third_party/capstone_asl/weights/phase_tcn_best_safe_state.pt"
BASELINE = REPO / "third_party/capstone_asl/weights/recognition_tcn_attention_best.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def feature_sequence(row, phase_model, phase_mean, phase_std, crop_mode):
    with np.load(row["landmarks"], allow_pickle=False) as d:
        pose, lh, rh = d["pose"], d["lh"], d["rh"]
        pm, lm, rm = d["pose_mask"], d["lh_mask"], d["rh_mask"]
    pts, pos = pipeline.robust_normalize_keypoints(pose, lh, rh, pm, lm, rm)
    vel, acc, gs, hs = pipeline.compute_motion_features(pts, pos)
    speed = pipeline.compute_phase_speed(pts, pos, gs, hs)
    x = np.concatenate((pos, vel, acc, gs[:, None], hs[:, None], speed[:, None]), 1).astype(np.float32)
    xn = np.nan_to_num((x - phase_mean) / phase_std)
    with torch.no_grad():
        p = torch.softmax(phase_model(torch.from_numpy(xn)[None].to(DEVICE)), -1)[0].cpu().numpy()
    pred = pipeline.majority_filter_1d(p.argmax(1))
    seg = pipeline.extract_phase_segments(pred, p, speed)
    if seg["segment_status"] == "reject":
        start, end, ordered = 0, len(x)-1, np.full(len(x), 2, np.int64)
    else:
        ordered = pipeline.make_ordered_labels(len(x), seg)
        if crop_mode == "full":
            start, end = 0, len(x)-1
        elif crop_mode == "stroke" and seg["stroke_end"] - seg["stroke_start"] + 1 >= 6:
            start, end = seg["stroke_start"], seg["stroke_end"]
        else:
            start, end = seg["active_start"], seg["active_end"]
    return x[start:end+1], ordered[start:end+1]


class Sequences(Dataset):
    def __init__(self, rows, mean, std, augment=False):
        self.rows, self.mean, self.std, self.augment = rows, mean, std, augment
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        x, phase, label = self.rows[i]
        x = np.nan_to_num((x-self.mean)/self.std).astype(np.float32)
        if self.augment:
            # Boundary jitter and light feature noise reduce dependence on the
            # exact automatic capture window without changing the sign label.
            left, right = random.randint(0, 3), random.randint(0, 3)
            if len(x) - left - right >= 12:
                x, phase = x[left:len(x)-right], phase[left:len(phase)-right]
            x = x + np.random.normal(0, 0.012, x.shape).astype(np.float32)
        x = np.concatenate((x, np.eye(4, dtype=np.float32)[phase]), 1)
        return torch.from_numpy(x), label


def collate(batch):
    length = max(len(x) for x, _ in batch); dim = batch[0][0].shape[1]
    xs = torch.zeros(len(batch), length, dim); mask = torch.zeros(len(batch), length, dtype=torch.bool)
    labels = torch.tensor([y for _, y in batch])
    for i, (x, _) in enumerate(batch): xs[i, :len(x)] = x; mask[i, :len(x)] = True
    return xs, mask, labels


def metrics(model, loader):
    model.eval(); correct = top5 = total = 0; pairs=[]; loss=0
    with torch.no_grad():
        for x, mask, y in loader:
            x, mask, y = x.to(DEVICE), mask.to(DEVICE), y.to(DEVICE)
            logits, _ = model(x, mask); loss += torch.nn.functional.cross_entropy(logits, y).item()*len(y)
            pred=logits.argmax(1); correct += (pred==y).sum().item(); total += len(y)
            top5 += (logits.topk(5,1).indices==y[:,None]).any(1).sum().item()
            pairs.extend(zip(y.cpu().tolist(), pred.cpu().tolist()))
    f1=[]
    for c in range(100):
        tp=sum(a==c and b==c for a,b in pairs); fp=sum(a!=c and b==c for a,b in pairs); fn=sum(a==c and b!=c for a,b in pairs)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return {"loss":loss/total,"top1":correct/total,"top5":top5/total,"macro_f1":sum(f1)/100,"count":total}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crop",choices=("full","active","stroke"),default="active")
    parser.add_argument("--experiment",default="default")
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--epochs",type=int,default=40)
    parser.add_argument("--patience",type=int,default=10)
    parser.add_argument("--learning-rate",type=float,default=8e-5)
    parser.add_argument("--label-smoothing",type=float,default=.06)
    parser.add_argument("--dropout",type=float,default=.40)
    parser.add_argument("--augment",action="store_true")
    args=parser.parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed); torch.set_num_threads(4)
    manifest_path=ROOT/"landmark-manifest.json"
    if not manifest_path.exists(): raise SystemExit("Extraction is not complete")
    rows=[r for r in json.loads(manifest_path.read_text()) if r.get("hand_frames",0)>=8 and r.get("pose_frames",0)>=8]
    label_rows=list(csv.DictReader(LABELS.open())); label_ids={r["gloss"]:int(r["rec_label_id"]) for r in label_rows}
    phase_ck=pipeline.load_checkpoint(PHASE,DEVICE); cfg=phase_ck["config"]
    phase_model=pipeline.PhaseTCN(cfg["input_dim"],cfg["num_classes"],cfg["hidden_dim"],cfg["num_blocks"],cfg["kernel_size"],cfg["dropout"]).to(DEVICE)
    phase_model.load_state_dict(phase_ck["model_state_dict"]); phase_model.eval()
    pmean=pipeline.to_numpy(phase_ck["feature_mean"]); pstd=np.maximum(pipeline.to_numpy(phase_ck["feature_std"]),1e-6)
    protocol_hash=hashlib.sha256((ROOT/"extraction-protocol.json").read_bytes()).hexdigest()[:12]
    cache=ROOT/f"recognition-features-{args.crop}-{protocol_hash}.pt"
    if cache.exists(): prepared=torch.load(cache,weights_only=False)
    else:
        prepared=[]
        for i,row in enumerate(rows,1):
            try:
                x,ph=feature_sequence(row,phase_model,pmean,pstd,args.crop); prepared.append((x,ph,label_ids[row["label"]],row["split"]))
            except Exception as e: print(f"skip {row['file']}: {e}")
            if i%100==0: print(f"features {i}/{len(rows)}",flush=True)
        torch.save(prepared,cache)
    train=[(x,p,y) for x,p,y,s in prepared if s=="train"]
    val=[(x,p,y) for x,p,y,s in prepared if s=="val"]
    base=pipeline.load_checkpoint(BASELINE,DEVICE); c=base["config"]
    # Preserve the feature scale on which the pretrained weights were learned.
    mean=pipeline.to_numpy(base["feature_mean"])
    std=np.maximum(pipeline.to_numpy(base["feature_std"]),1e-6)
    tr=DataLoader(Sequences(train,mean,std,args.augment),batch_size=16,shuffle=True,collate_fn=collate)
    va=DataLoader(Sequences(val,mean,std),batch_size=16,shuffle=False,collate_fn=collate)
    model=pipeline.RecognitionTCNAttentionSafe(c["input_dim"],100,c["hidden_dim"],c["num_blocks"],c["kernel_size"],c["dropout"],c["attention_dropout"]).to(DEVICE)
    model.load_state_dict(base["model_state_dict"])
    for module in model.modules():
        if isinstance(module, torch.nn.Dropout):
            module.p=args.dropout
    baseline_score=metrics(model,va); print(json.dumps({"baseline":baseline_score}),flush=True)
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.learning_rate,weight_decay=3e-4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs,eta_min=1e-6)
    counts=np.bincount([y for _,_,y in train],minlength=100); weights=torch.tensor(len(train)/(100*np.maximum(counts,1)),dtype=torch.float32,device=DEVICE)
    suffix=f"{args.crop}-{args.experiment}"
    best=None; stale=0; out=ROOT/f"recognition_tcn_attention_candidate_{suffix}.pt"
    for epoch in range(1,args.epochs+1):
        model.train(); running=0
        for x,mask,y in tr:
            x,mask,y=x.to(DEVICE),mask.to(DEVICE),y.to(DEVICE); optimizer.zero_grad()
            logits,_=model(x,mask); loss=torch.nn.functional.cross_entropy(
                logits,y,weight=weights,label_smoothing=args.label_smoothing)
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1); optimizer.step(); running+=loss.item()*len(y)
        scheduler.step()
        score=metrics(model,va); print(json.dumps({"epoch":epoch,"train_loss":running/len(train),**score}),flush=True)
        key=(score["top1"],score["macro_f1"])
        if best is None or key>best:
            best=key; stale=0
            torch.save({"epoch":epoch,"model_state_dict":model.state_dict(),"config":c,
                        "feature_mean":torch.from_numpy(mean),"feature_std":torch.from_numpy(std),
                        "class_weights":weights.cpu(),"val_top1":score["top1"],"val_top5":score["top5"],
                        "val_macro_f1":score["macro_f1"],"training_source":"ASL Citizen official train split",
                        "selection_source":"ASL Citizen official validation split",
                        "experiment":vars(args)},out)
        else:
            stale+=1
            if stale>=args.patience: break
    report={"train":len(train),"validation":len(val),"baseline":baseline_score,
            "best_top1":best[0],"best_macro_f1":best[1],
            "passes_baseline":best[0]>baseline_score["top1"] and best[1]>=baseline_score["macro_f1"],
            "crop":args.crop,"experiment":vars(args),"checkpoint":str(out)}
    (ROOT/f"training-result-{suffix}.json").write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps(report,indent=2))


if __name__=="__main__": main()
