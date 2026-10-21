"""Train a compact signer-separated PCA/SVM baseline for CAPSTONE100."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import joblib
import numpy as np
import torch
from sklearn.decomposition import PCA
from sklearn.metrics import accuracy_score, f1_score, top_k_accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT=Path("/opt/handspeak-training/capstone100-retrain")

def vector(x):
    # Preserve absolute hand/body geometry and motion at 20 temporal samples.
    indices=np.linspace(0,len(x)-1,20).round().astype(int)
    return np.asarray(x,dtype=np.float32)[indices].reshape(-1)

def main():
    protocol=hashlib.sha256((ROOT/"extraction-protocol.json").read_bytes()).hexdigest()[:12]
    rows=torch.load(ROOT/f"recognition-features-full-{protocol}.pt",weights_only=False)
    train=[(vector(x),y) for x,_,y,s in rows if s=="train"]
    val=[(vector(x),y) for x,_,y,s in rows if s=="val"]
    xtr=np.stack([x for x,_ in train]); ytr=np.asarray([y for _,y in train])
    xva=np.stack([x for x,_ in val]); yva=np.asarray([y for _,y in val])
    model=Pipeline([
        ("scale",StandardScaler()),
        ("pca",PCA(n_components=256,whiten=True,svd_solver="randomized",random_state=42)),
        ("svm",SVC(C=5.0,kernel="rbf",gamma="scale",class_weight="balanced",
                   probability=True,random_state=42,cache_size=2048)),
    ])
    model.fit(xtr,ytr)
    probabilities=model.predict_proba(xva)
    classes=model.named_steps["svm"].classes_
    prediction=classes[probabilities.argmax(1)]
    result={
      "train":len(train),"validation":len(val),"features":int(xtr.shape[1]),
      "top1":float(accuracy_score(yva,prediction)),
      "top5":float(top_k_accuracy_score(yva,probabilities,labels=classes,k=5)),
      "macro_f1":float(f1_score(yva,prediction,labels=np.arange(100),average="macro",zero_division=0)),
      "protocol":protocol,
    }
    target=ROOT/"capstone100-pca-svm.joblib"; joblib.dump(model,target,compress=3)
    result["model"]=str(target); result["bytes"]=target.stat().st_size
    (ROOT/"pca-svm-validation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
