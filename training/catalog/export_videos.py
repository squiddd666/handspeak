"""Export attributed practice clips from development recordings only."""
import sys,json,subprocess,hashlib
from pathlib import Path
import imageio_ffmpeg
ROOT=Path('/opt/handspeak-training/vocabulary-v7');SITE=Path('/opt/handspeak/repository')
if __name__=='__main__':
 catalog=json.loads((SITE/'models/motion-vocabulary.json').read_text());rows=json.loads((ROOT/'development-manifest.json').read_text());credits=[]
 for item in catalog['items']:
  if item.get('video'):continue
  candidates=[r for r in rows if r['label']==item['label'] and r['split']=='train']
  if not candidates:continue
  r=candidates[0];destination=SITE/'media/signs'/(item['id']+'.mp4')
  if not destination.exists():subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-threads','1','-i',r['file'],'-vf','scale=480:-2','-filter_threads','1','-an','-c:v','libx264','-threads','1','-preset','fast','-crf','26','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(destination)],check=True)
  item['video']='media/signs/'+destination.name
  credits.append({'label':item['label'],'video':item['video'],'source':r['source'],'member':r['member'],'sourceSha256':r['sha256'],'videoSha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'license':'CC BY 4.0','attribution':'PopSign ASL v1.0, Georgia Tech and DPAN','changes':'Resized to 480 pixels wide, compressed H.264, audio removed. Original timing retained.'})
 (SITE/'models/motion-vocabulary.json').write_text(json.dumps(catalog,indent=2)+'\n');(ROOT/'video-sources.json').write_text(json.dumps(credits,indent=2));print('Exported',len(credits),flush=True)
