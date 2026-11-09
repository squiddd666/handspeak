"""Decode every acquired frame into pixels; retain failed originals, no inference."""
import argparse, collections, concurrent.futures, json, math
from pathlib import Path
from scripts.prepare_online_motion_audit import write_new
from scripts.run_online_native_audit import sha  # Streaming SHA also supports the vision environment's Python 3.10.
import cv2


def check(row):
    result=dict(auditId=row['auditId'],label=row['label'],downloadStatus=row['status'],auditEligible=row['auditEligible'],fullDecodePassed=False)
    if row['status']!='downloaded': return result
    path=Path(row['path']); result.update(sha256Verified=sha(path)==row['sha256'],byteSizeVerified=path.stat().st_size==row['byteSize'])
    cap=cv2.VideoCapture(str(path)); count=0; shapes=set()
    try:
        result.update(opened=cap.isOpened(),width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=cap.get(cv2.CAP_PROP_FPS),declaredFrames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        while True:
            ok,frame=cap.read()  # retrieve real pixels for EVERY frame, not only grab().
            if not ok: break
            if frame is None or not frame.size: raise ValueError('Decoder returned empty pixels')
            shapes.add(tuple(frame.shape)); count+=1
        result.update(decodedFrames=count,decodedShapes=[list(s) for s in sorted(shapes)])
        result['durationSeconds']=count/result['fps'] if math.isfinite(result['fps']) and result['fps']>0 else None
        result['fullDecodePassed']=bool(result['opened'] and result['sha256Verified'] and result['byteSizeVerified'] and count>0 and count==result['declaredFrames'] and len(shapes)==1)
    except Exception as e: result['error']=str(e)
    finally: cap.release()
    print(row['auditId'],count,'frames',result['fullDecodePassed'],flush=True); return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--folder',type=Path,required=True); a=p.parse_args()
    rows=json.loads((a.folder/'downloads.json').read_text('utf-8'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(check,rows))
    summary=dict(files=len(rows),decodedFrames=sum(r.get('decodedFrames',0) for r in results),
        fullDecodePassed=sum(r['fullDecodePassed'] for r in results),failuresRetained=[r['auditId'] for r in results if not r['fullDecodePassed']],
        predictionsRun=False,decodeUsedForSelection=False,videosModified=False,cv2Version=cv2.__version__,
        downloadsSha256=sha(a.folder/'downloads.json'))
    write_new(a.folder/'video-integrity.json',dict(summary=summary,files=results)); print(json.dumps(summary,indent=2))
