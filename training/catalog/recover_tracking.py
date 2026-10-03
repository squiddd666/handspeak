"""Retry development tracking failures with 60 real frames; no synthetic interpolation for training."""
import json,sys,subprocess,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import cv2,imageio_ffmpeg
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dense_extract import extract
ROOT=Path('/opt/handspeak-training/vocabulary-v7')
def job(row):
 original=Path(row['file']);scaled=ROOT/'dense-corrected'/row['split']/row['sourceLabel']/original.name;scaled.parent.mkdir(parents=True,exist_ok=True)
 if not scaled.exists():
  cap=cv2.VideoCapture(str(original));n=cap.get(cv2.CAP_PROP_FRAME_COUNT);fps=cap.get(cv2.CAP_PROP_FPS);cap.release();duration=n/max(fps,1)
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-threads','1','-i',str(original),'-vf','scale=480:-2','-filter_threads','1','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-fps_mode','passthrough','-y',str(scaled)],check=True)
 result=extract({**row,'file':str(scaled)});return {**row,**{k:result[k] for k in ['sequence','rawFrames','frames','trackedFrames','imageAspect']},'recoveryFile':str(scaled),'recoverySha256':hashlib.sha256(scaled.read_bytes()).hexdigest()}
if __name__=='__main__':
 rows=json.loads((ROOT/'development-features.json').read_text());failed=[r for r in rows if r.get('sequence') is None];recovered=[]
 with ProcessPoolExecutor(max_workers=3) as pool:
  for r in pool.map(job,failed):
   recovered.append(r)
   if len(recovered)%20==0:print('Dense retry',len(recovered),'/',len(failed),'recovered',sum(bool(x['sequence']) for x in recovered),flush=True)
 lookup={r['sha256']:r for r in recovered};updated=[lookup.get(r['sha256'],r) for r in rows]
 (ROOT/'dense-development-features.json').write_text(json.dumps(updated,separators=(',',':')));print('Recovered',sum(bool(x['sequence']) for x in recovered),'of',len(failed),flush=True)
