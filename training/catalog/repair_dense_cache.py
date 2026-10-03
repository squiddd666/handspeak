"""Repair temporally upsampled short-clip retries without altering archived failed experiments."""
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from recover_tracking import job
ROOT=Path('/opt/handspeak-training/vocabulary-v7');OUT=Path('/opt/handspeak-training/vocabulary-v8')
if __name__=='__main__':
 audit=json.loads((OUT/'dense-source-frame-audit.json').read_text());bad={r['sha256'] for r in audit['under60Frames']};rows=json.loads((ROOT/'dense-development-features.json').read_text());fixed=[]
 with ProcessPoolExecutor(max_workers=3) as pool:
  for r in pool.map(job,[r for r in rows if r['sha256'] in bad]):
   fixed.append(r)
   if len(fixed)%20==0:print('Repaired',len(fixed),'/',len(bad),flush=True)
 lookup={r['sha256']:r for r in fixed};corrected=[lookup.get(r['sha256'],r) for r in rows];original=json.loads((ROOT/'development-features.json').read_text());prior=sum(bool(r.get('sequence')) for r in original)
 (ROOT/'corrected-development-features.json').write_text(json.dumps(corrected,separators=(',',':')))
 report={'affectedDevelopmentClips':len(bad),'previousClaimedRecovery':sum(bool(r.get('sequence')) for r in rows)-prior,'correctedRecovery':sum(bool(r.get('sequence')) for r in corrected)-prior,'correctedUsableSequences':sum(bool(r.get('sequence')) for r in corrected),'method':'Short clips re-encoded with temporal passthrough and unique-frame selection; no repeated-frame padding. Longer prior retries downsampled source videos to 60 frames. Archived v8/v9 experiments remain unpromoted and must not be used to claim improvement.'};(OUT/'recovery-correction.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
