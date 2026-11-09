"""Generate an explicitly experimental, virtual-only capture-contract fixture."""
import hashlib,json,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    name='motion-dual-capture-v7-20261107.html';target=ROOT/name
    if target.exists():raise FileExistsError(target)
    items=json.loads((ROOT/'models/recognition-videos.json').read_text(encoding='utf-8'))['items']
    candidate='reports/motion-repair-v5-20261107/candidates/body-manual-24.json'
    files=['landmark-capture.js','body-hand-recovery.js','hand-recovery-worker.js','camera-performance.js','motion-model.js',
           'gesture-model.js','expanded-motion.js','hello-binary.js','temporal-motion/temporal-features.js',
           'training/experimental/dual_capture.mjs','training/experimental/dual_hand_worker.js','training/experimental/dual_capture_page.mjs',
           'training/experimental/body_manual_runtime.mjs',candidate,'models/asl-words.json','models/asl-extra-words.json',
           'models/hello-binary.json','models/baby-binary.json','models/water-binary.json']
    refs=[dict(id=i['id'],label=i['label'],video=i['video'],videoSha256=sha(ROOT/i['video'])) for i in items]
    config=dict(items=refs,candidate=candidate,filesSha256={p:sha(ROOT/p) for p in files},token=secrets.token_urlsafe(32))
    config['fixtureSha256']=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Isolated dual-capture diagnostics</title>
<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px;color:#eee;background:#142024}button,input,select{font:inherit;padding:8px;margin:6px}video,canvas{width:240px;height:180px;background:#101010}pre{max-height:350px;overflow:auto;font-size:12px}label{display:block}#status{padding:15px;background:#254840}</style></head><body>
<h1>VIRTUAL-ONLY dual-capture diagnostics</h1><p>Physical camera and microphone are blocked. This isolated fixture uses the original body recording service plus an experimental independent hand stream. Production app, weights and gates are unchanged. This is not recognition accuracy or full app-routing verification.</p>
<video id="source" muted playsinline controls></video><canvas id="virtualCanvas" width="960" height="720" aria-label="Virtual reference source"></canvas><video id="virtualCamera" muted playsinline aria-label="Virtual camera only"></video>
<label>Reference <select id="reference"></select></label><button id="arm">Arm reference</button><button id="record" disabled>Record dual streams</button><button id="cancel" disabled>Cancel diagnostic capture</button><button id="blank">Blank virtual reference</button>
<label>Manual vocabulary <select id="manualMode"><option value="default">Default words</option><option value="expanded">Expanded words</option></select></label>
<p id="status" role="status">Loading frozen models…</p><p id="summary"></p><p id="saved"></p>
<label>Diagnostic reference IDs <input id="ids" value="hello no hungry finish please book pain apple"></label><button id="batch">Run dual-capture diagnostics</button><button id="stop">Stop diagnostic batch</button><p id="batchStatus"></p>
<details><summary>Scalar-only capture ledger</summary><pre id="ledger"></pre></details>
<script>window.DUAL_CAPTURE_FIXTURE = CONFIG;</script><script type="module" src="training/experimental/dual_capture_page.mjs"></script></body></html>'''
    target.write_text(html.replace('CONFIG',json.dumps(config)),encoding='utf-8')
    print(json.dumps(dict(fixture=str(target),url='http://127.0.0.1:8008/'+name,fixtureSha256=config['fixtureSha256']),indent=2))
if __name__=='__main__':main()
