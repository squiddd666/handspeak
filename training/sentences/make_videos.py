import json,subprocess,hashlib
from pathlib import Path
import imageio_ffmpeg
root=Path('/opt/handspeak/repository');work=Path('/opt/handspeak-training/vocabulary-v6');rows=json.loads((work/'development-features.json').read_text());assets=root/'media/signs';sources=json.loads((assets/'sources.json').read_text())
for label in ['FOOD','HUNGRY','LIKE','GO']:
 row=next(r for r in rows if r['label']==label and r['split']=='train' and r['sequence']);out=assets/(label.lower()+'.mp4')
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-threads','1','-i',row['file'],'-vf','scale=480:-2','-an','-c:v','libx264','-threads','1','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(out)],check=True)
 sources=[s for s in sources if s['label']!=label];sources.append(dict(label=label,source=row['source'],member=row['member'],sha256=row['sha256'],file=out.name,derivedSha256=hashlib.sha256(out.read_bytes()).hexdigest()))
(assets/'sources.json').write_text(json.dumps(sources,indent=2)+'\n');p=assets/'README.md';p.write_text(p.read_text().replace('Nine selected','Thirteen selected').replace('resized to 480×640','resized to 480-pixel width'))
print('Added four practice videos')
