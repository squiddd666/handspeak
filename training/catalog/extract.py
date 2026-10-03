"""Resize originals for cheaper decoding, then use the unchanged browser feature encoder."""
import sys,json,hashlib,subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,'/opt/handspeak/repository/training')
from train_words import extract
import cv2,imageio_ffmpeg
ROOT=Path('/opt/handspeak-training/vocabulary-v7')
def job(row):
 original=Path(row['file']);old=original.with_suffix('.landmarks.json')
 if old.exists():return {**extract(row),**row}
 scaled=ROOT/'processed-native'/row['split']/row['sourceLabel']/original.name;scaled.parent.mkdir(parents=True,exist_ok=True)
 if not scaled.exists():
  cap=cv2.VideoCapture(str(original));n=cap.get(cv2.CAP_PROP_FRAME_COUNT);fps=cap.get(cv2.CAP_PROP_FPS);cap.release();duration=n/max(fps,1)
  if duration<=0:raise ValueError('Invalid video duration')
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-threads','1','-i',str(original),'-vf','scale=480:-2','-filter_threads','1','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-fps_mode','passthrough','-y',str(scaled)],check=True)
 result=extract({**row,'file':str(scaled)});return {**result,**row,'processedFile':str(scaled),'processedSha256':hashlib.sha256(scaled.read_bytes()).hexdigest()}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true');args=parser.parse_args();prefix='test' if args.test else 'development'
 rows=json.loads((ROOT/(prefix+'-manifest.json')).read_text());out=[]
 with ProcessPoolExecutor(max_workers=3) as pool:
  for r in pool.map(job,rows):
   out.append(r)
   if len(out)%20==0:print('Extracted',prefix,len(out),'/',len(rows),flush=True)
 (ROOT/(prefix+'-features.json')).write_text(json.dumps(out,separators=(',',':')));print('Complete',prefix,len(out),flush=True)
