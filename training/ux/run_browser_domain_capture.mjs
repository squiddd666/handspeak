// Owned headless browser, TRAIN/VAL capture only. Never user Chrome or APIs.
import {spawn} from 'node:child_process';
import {createWriteStream,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {createHash} from 'node:crypto';
const file=resolve(process.argv[2]),folder=dirname(file),root=process.cwd(),protocol=JSON.parse(readFileSync(file,'utf8'));
const ALLOWED=new Set(['browser-detector-domain-train-val-feature-capture','phone-domain-train-val-feature-capture','full-family-body-domain-train-val-feature-capture']);
if(!ALLOWED.has(protocol.purpose))throw new Error('Wrong protocol');
const verifyAll=()=>{for(const [path,digest] of Object.entries(protocol.frozenFilesSha256))if(createHash('sha256').update(readFileSync(path)).digest('hex')!==digest)throw new Error('Frozen input changed: '+path);};
verifyAll();const site=`http://127.0.0.1:${protocol.port}`,debug=`http://127.0.0.1:${protocol.debugPort}`;
for(const url of [site,debug]){let occupied=false;try{await (await fetch(url)).arrayBuffer();occupied=true;}catch{}if(occupied)throw new Error('Occupied port; refusing existing service: '+url);}
const profile=resolve(folder,'headless-profile');if(existsSync(profile))throw new Error('Profile already used; no source rerun');mkdirSync(profile);
const serverLog=createWriteStream(resolve(folder,'browser-server.log')),chromeLog=createWriteStream(resolve(folder,'headless-chrome.log'));
const server=spawn(resolve(root,'../hs-eval/.venv/Scripts/python.exe'),['-u','-m','scripts.serve_browser_domain_capture','--protocol',file],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
server.stdout.pipe(serverLog);server.stderr.pipe(serverLog);let serverExit=null;server.once('exit',(code,signal)=>{serverExit={code,signal};});
let chrome,ws,send,evaluate,events=[];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function ready(url,timeout){const end=Date.now()+timeout;while(Date.now()<end){try{const r=await fetch(url);await r.arrayBuffer();if(r.ok)return;}catch{}await sleep(500);}throw new Error('Infrastructure unavailable: '+url);}
try{
  await ready(site+'/fixture.html',60000);const checks={};
  for(const path of ['/api/beginner-asl/status','/api/capstone-asl/status','/api/auth/me','/handspeak.db','/../handspeak.db','/features/checkpoint.json']){
    const r=await fetch(site+path);await r.arrayBuffer();if(r.status!==404)throw new Error('Feature server allowlist leaked: '+path);checks[path]=404;
  }
  const blocked=await fetch(site+'/__domain__/feature',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  await blocked.arrayBuffer();if(blocked.status!==403)throw new Error('Unauthorized save not blocked');checks.unauthorizedPost=403;
  const cfg=JSON.parse(readFileSync(resolve(folder,'fixture.json'),'utf8'));
  const range=await fetch(site+cfg.items[0].video,{headers:{Range:'bytes=0-31'}}),bytes=await range.arrayBuffer();
  if(range.status!==206||bytes.byteLength!==32)throw new Error('Original media range failed');checks.mediaRange=206;
  writeFileSync(resolve(folder,'infrastructure-checks.json'),JSON.stringify(checks,null,2));
  chrome=spawn(protocol.chromeExecutable,[`--user-data-dir=${profile}`,'--headless=new','--remote-debugging-address=127.0.0.1',`--remote-debugging-port=${protocol.debugPort}`,
    '--disable-quic','--no-first-run','--no-default-browser-check','--autoplay-policy=no-user-gesture-required',
    '--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows',
    '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  chrome.stdout.pipe(chromeLog);chrome.stderr.pipe(chromeLog);await ready(debug+'/json/version',30000);
  const page=(await (await fetch(debug+'/json/list')).json()).find(t=>t.type==='page');
  ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  let serial=0;const pending=new Map();
  ws.addEventListener('message',event=>{const d=JSON.parse(event.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.timer);d.error?p.reject(new Error(JSON.stringify(d.error))):p.resolve(d.result);}else if(['Runtime.exceptionThrown','Log.entryAdded','Network.loadingFailed'].includes(d.method))events.push(d);});
  send=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},60000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||'Capture script failed');return r.result.value;};
  await send('Runtime.enable');await send('Log.enable');await send('Network.enable');await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1200,height:900,deviceScaleFactor:1,mobile:false});
  writeFileSync(resolve(folder,'browser-version.json'),JSON.stringify(await send('Browser.getVersion'),null,2));
  await send('Page.navigate',{url:site+'/fixture.html'});let loaded=false;
  for(const end=Date.now()+180000;Date.now()<end;){
    if(serverExit)throw new Error('Owned server exited: '+JSON.stringify(serverExit));
    if(await evaluate("document.body?.dataset.auditReady==='true'")){loaded=true;break;}await sleep(1000);
  }
  if(!loaded)throw new Error('Graphs did not initialize without images; capture not started');verifyAll();
  await evaluate("document.getElementById('batch').click();true");let previous='',done=false;
  for(const end=Date.now()+21600000;Date.now()<end;){
    if(serverExit)throw new Error('Owned server exited: '+JSON.stringify(serverExit));
    const state=await evaluate("({saved:document.getElementById('saved').textContent,status:document.getElementById('status').textContent,batch:document.getElementById('batchStatus').textContent})");
    if(state.saved!==previous){previous=state.saved;console.log(state.saved,state.status);}
    if(state.batch.startsWith('Needs attention:'))throw new Error(state.batch);
    if(state.batch.startsWith('Batch finished:')){
      const rows=JSON.parse(readFileSync(resolve(folder,'features/checkpoint.json'),'utf8'));
      if(rows.length!==protocol.order.length||rows.some((r,i)=>r.id!==protocol.order[i]))throw new Error('Incomplete/wrong immutable ledger');
      for(const r of rows)if(createHash('sha256').update(readFileSync(r.path)).digest('hex')!==r.sha256)throw new Error('Feature changed: '+r.path);
      verifyAll();writeFileSync(resolve(folder,'post-run-integrity.json'),JSON.stringify({allFrozenFilesUnchanged:true,files:Object.keys(protocol.frozenFilesSha256).length,allFeaturesUnchanged:true,features:rows.length},null,2));
      writeFileSync(resolve(folder,'capture-summary.json'),JSON.stringify({sources:rows.length,contractsPassed:rows.filter(r=>r.contractPassed).length,failed:rows.filter(r=>!r.contractPassed).length,
        bodyFrames:rows.reduce((n,r)=>n+r.bodyFrames,0),pairedFrames:rows.reduce((n,r)=>n+r.pairCount,0),physicalCameraCalls:0,microphoneCalls:0,predictionsRun:false,scope:'Separate TRAIN/VAL detector-domain development, not recognition accuracy.'},null,2));
      const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(resolve(folder,'browser-proof.png'),Buffer.from(shot.data,'base64'));done=true;
      console.log('Completed',rows.length,'TRAIN/VAL captures, no recognition predictions.');break;
    }await sleep(2000);
  }if(!done)throw new Error('Capture deadline exceeded; durable partial features retained');
}finally{
  if(evaluate)try{writeFileSync(resolve(folder,'final-page-state.json'),JSON.stringify(await evaluate("({active:document.body.dataset.activeCapture??null,outcome:document.body.dataset.captureOutcome??null,status:document.getElementById('status')?.textContent,batch:document.getElementById('batchStatus')?.textContent,saved:document.getElementById('saved')?.textContent})"),null,2));}catch{}
  writeFileSync(resolve(folder,'browser-console.json'),JSON.stringify(events,null,2));try{if(send)await send('Browser.close');}catch{}try{ws?.close();}catch{}
  chrome?.kill();server.kill();await sleep(1500);serverLog.end();chromeLog.end();
  const cleanup={};for(const [name,url] of Object.entries({server:site,browser:debug})){try{await fetch(url);cleanup[name]='still responds';}catch{cleanup[name]='no response';}}
  writeFileSync(resolve(folder,'cleanup-receipt.json'),JSON.stringify(cleanup,null,2));
}
