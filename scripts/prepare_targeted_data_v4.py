"""Select official split-preserving recordings for targeted repair.

No Watch source is a fitting or independent-test input. Existing recordings
are identified as re-extractions, not advertised as new independent data.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
EVAL=REPO.parent/"hs-eval"
MANUAL={"HELLO":["HELLO"],"THANK YOU":["THANKYOU"],"PLEASE":["PLEASE"],"YES":["YES"],
        "NO":["NO"],"FINISH":["FINISH"],"DRINK":["DRINK1","DRINK2"],"WATER":["WATER"],
        "BOOK":["BOOK"],"FOOD":["EAT1"],"HUNGRY":["HUNGRY"],"LIKE":["LIKE"],"GO":["GO"],
        "NAME":["NAME"],"HOME":["HOME"],"HAVE":["HAVE"],"WANT":["WANT1","WANT2"],
        "LOVE":["LOVE"],"FISH":["FISH"],"PAIN":["PAIN"],"SEE":["SEE"],"SICK":["SICK"],
        "NIGHT":["NIGHT1","NIGHT2"],"BABY":["BABY1","BABY2"]}


def rows(path):return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def prepare(out):
    if out.exists():raise FileExistsError(out)
    catalog=json.loads((REPO/"models/motion-vocabulary.json").read_text(encoding="utf-8"))["items"]
    manifest=json.loads((REPO/"models/recognition-videos.json").read_text(encoding="utf-8"))
    watch={s["originalFile"] for r in manifest["items"] for s in r.get("sources",[])}
    failures=json.loads((REPO/"reports/motion-repair-v3-20261107/remaining-reference-failures.json").read_text(encoding="utf-8"))
    regressions=json.loads((REPO/"reports/motion-repair-v3-20261107/previous-match-regressions.json").read_text(encoding="utf-8"))
    targets={r["label"] for r in failures if r.get("prediction") or "Not enough" in r.get("status","")}
    targets.update(r["label"] for r in regressions)
    # Include competing classes, never only positive examples of failed words.
    targets.update(["MY / MINE","THEY","YOUR / YOURS","WAIT","WALK","DEVELOP"])
    old_beginner=rows(EVAL/"motion-repair-20261107/features-beginner-repaired.jsonl")
    old_full=rows(EVAL/"features-train-merged.jsonl")+rows(EVAL/"features-test-merged.jsonl")
    old={Path(r["file"]).name for r in old_beginner+old_full}
    for filename in ("sequences.json","pack-sequences.json","night-sequences.json"):
        old.update(Path(r["file"]).name for r in json.loads((EVAL/"daily-words"/filename).read_text(encoding="utf-8")))
    beginner_gloss={}
    for r in old_beginner:
        if not r.get("syntheticGreeting"):
            beginner_gloss.setdefault(r.get("sourceGloss") or r["gloss"],r["label"])
    full_gloss={r["gloss"] for r in old_full}
    glosses={g for r in catalog if r["label"] in targets for g in r.get("modelGlosses",[])}
    glosses.update(g for g,label in beginner_gloss.items() if label in targets)
    manual_gloss={g:label for label,gs in MANUAL.items() for g in gs}
    glosses.update(manual_gloss)
    cache_roots=[EVAL/"cache/train-val",EVAL/"cache/videos",EVAL/"beginner-100/videos",
                 EVAL/"daily-words/videos",EVAL/"daily-words/pack-clips"]
    cached={p.name:p.resolve() for root in cache_roots for p in root.rglob("*.mp4")}
    selected=[];participant_splits=collections.defaultdict(set)
    for split in ("train","val","test"):
        table=list(csv.DictReader((EVAL/"cache"/f"{split}.csv").open(encoding="utf-8-sig")))
        for r in sorted(table,key=lambda r:(r["Gloss"],r["Participant ID"],r["Video file"])):
            file=r["Video file"];gloss=r["Gloss"]
            if gloss not in glosses or file in watch:continue
            participant=r["Participant ID"];participant_splits[participant].add(split)
            record={"file":file,"gloss":gloss,"split":split,"participant":participant,
                    "member":"ASL_Citizen/videos/"+file,"source":"ASL Citizen",
                    "lexCode":r.get("ASL-LEX Code"),"previouslyExtracted":file in old}
            if gloss in manual_gloss:record["manualLabel"]=manual_gloss[gloss]
            if gloss in beginner_gloss:record["beginnerLabel"]=beginner_gloss[gloss]
            if gloss in full_gloss:record["capstoneLabel"]=gloss
            path=cached.get(file) or (EVAL/"motion-repair-v4-20261107/videos"/split/file).resolve()
            record["path"]=str(path);record["cached"]=path.exists()
            selected.append(record)
    if any(len(s)>1 for s in participant_splits.values()):raise ValueError("Signer split leakage")
    if len({r["file"] for r in selected})!=len(selected):raise ValueError("Duplicate source")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(selected,indent=2)+"\n",encoding="utf-8")
    audit={"sources":len(selected),"bySplit":dict(collections.Counter(r["split"] for r in selected)),
           "manualLabels":list(MANUAL),"targetedLabels":sorted(targets),
           "notPreviouslyExtracted":sum(not r["previouslyExtracted"] for r in selected),
           "cached":sum(r["cached"] for r in selected),"watchExcluded":True,"signersDisjoint":True,
           "manifestSha256":hashlib.sha256(out.read_bytes()).hexdigest(),
           "aliases":{"EAT1":"FOOD: ASL food/eat lexical synonym in the manual English-label vocabulary"}}
    out.with_suffix(".audit.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=EVAL/"motion-repair-v4-20261107/selection.json")
    prepare(parser.parse_args().out)
