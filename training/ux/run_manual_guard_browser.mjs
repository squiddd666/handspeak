// Developer-owned headless test browser only. Never attach a user browser.
import {spawn} from 'node:child_process';
import {createWriteStream,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {createHash} from 'node:crypto';
const file=resolve(process.argv[2]),folder=dirname(file),root=process.cwd(),protocol=JSON.parse(readFileSync(file,'utf8'));
const verifyAll=()=>{for(const [path,digest] of Object.entries(protocol.frozenFilesSha256))if(createHash('sha256').update(readFileSync(path)).digest('hex')!==digest)throw new Error('Frozen input changed: '+path);};
const site='http://127.0.0.1:8011',debug='http://127.0.0.1:9231';
for(const [path,digest] of Object.entries(protocol.frozenFilesSha256))if(createHash('sha256').update(readFileSync(path)).digest('hex')!==digest)throw new Error('Frozen input changed: '+path);
for(const url of [site,debug]){let occupied=false;try{const response=await fetch(url);await response.arrayBuffer();occupied=true;}catch{}if(occupied)throw new Error('Audit port occupied; refusing to attach an existing service: '+url);}
const profile=resolve(folder,'headless-profile');if(existsSync(profile))throw new Error('Profile already used; no best-of browser rerun');mkdirSync(profile);
const serverLog=createWriteStream(resolve(folder,'browser-server.log')),chromeLog=createWriteStream(resolve(folder,'headless-chrome.log'));
const python=resolve(root,'../hs-eval/.venv/Scripts/python.exe');
const server=spawn(python,['-u','-m','scripts.serve_manual_guard_browser','--protocol',file],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
server.stdout.pipe(serverLog);server.stderr.pipe(serverLog);
let chrome,ws,send,events=[],serverExit=null;
server.once('exit',(code,signal)=>{serverExit={code,signal};});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function ready(url,timeout){const end=Date.now()+timeout;while(Date.now()<end){try{const r=await fetch(url);await r.arrayBuffer();if(r.ok)return r;}catch{}await sleep(500);}throw new Error('Audit infrastructure unavailable: '+url);}
try {
  await ready(site+'/fixture.html',60000);
  // Infrastructure-only checks: no landmarks/images or expected-label hints.
  const checks={};
  for(const [name,path,expected] of [['beginner','/api/beginner-asl/status',79],['capstone','/api/capstone-asl/status',100]]){
    const r=await fetch(site+path),s=await r.json();
    if(!r.ok||!s.available||s.labels?.length!==expected||s.checkpointSha256!==protocol.productionStatus[name].checkpointSha256)throw new Error('Production status mismatch');
    checks[name]={available:s.available,labels:s.labels.length,checkpointSha256:s.checkpointSha256};
  }
  for(const path of ['/api/auth/me','/api/admin/database-access','/handspeak.db','/../handspeak.db']){
    const r=await fetch(site+path);await r.arrayBuffer();if(r.status!==404)throw new Error('Audit allowlist leaked: '+path);checks[path]=r.status;
  }
  const blocked=await fetch(site+'/api/beginner-asl',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"consent":true,"frames":[]}'});
  await blocked.arrayBuffer();if(blocked.status!==403)throw new Error('Missing token/origin not blocked');checks.unauthorizedPost=blocked.status;
  const cfg=JSON.parse(readFileSync(resolve(folder,'fixture.json'),'utf8'));
  const range=await fetch(site+cfg.items[0].video,{headers:{Range:'bytes=0-31'}}),bytes=await range.arrayBuffer();
  if(range.status!==206||bytes.byteLength!==32||!range.headers.get('Content-Range')?.startsWith('bytes 0-31/'))throw new Error('Original media ranges not supported');
  checks.mediaRange=206;writeFileSync(resolve(folder,'infrastructure-checks.json'),JSON.stringify(checks,null,2));
  chrome=spawn(protocol.chromeExecutable,[`--user-data-dir=${profile}`,'--headless=new','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9231',
    '--disable-quic','--no-first-run','--no-default-browser-check','--autoplay-policy=no-user-gesture-required',
    '--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows',
    '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  chrome.stdout.pipe(chromeLog);chrome.stderr.pipe(chromeLog);
  await ready(debug+'/json/version',30000);
  const targets=await (await fetch(debug+'/json/list')).json(),page=targets.find(target=>target.type==='page');
  ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  let serial=0;const pending=new Map();
  ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.id&&pending.has(data.id)){const p=pending.get(data.id);pending.delete(data.id);clearTimeout(p.timer);data.error?p.reject(new Error(JSON.stringify(data.error))):p.resolve(data.result);}else if(['Runtime.exceptionThrown','Log.entryAdded','Network.loadingFailed'].includes(data.method))events.push(data);});
  send=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},60000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||'Audit script failed');return r.result.value;};
  await send('Runtime.enable');await send('Log.enable');await send('Network.enable');await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1200,height:900,deviceScaleFactor:1,mobile:false});
  const version=await send('Browser.getVersion');writeFileSync(resolve(folder,'browser-version.json'),JSON.stringify(version,null,2));
  await send('Page.navigate',{url:site+'/fixture.html'});
  let loaded=false;const bootDeadline=Date.now()+180000;
  while(Date.now()<bootDeadline){
    if(serverExit)throw new Error('Owned server exited during bootstrap: '+JSON.stringify(serverExit));
    if(await evaluate("document.body?.dataset.auditReady==='true'")){loaded=true;break;}await sleep(1000);
  }
  if(!loaded)throw new Error('Detectors/models did not initialize without images; recognition audit not started');
  verifyAll();
  await evaluate("document.getElementById('batch').click();true");
  const end=Date.now()+1800000;let previous='';
  while(Date.now()<end){
    const state=await evaluate("({summary:document.getElementById('summary')?.textContent,status:document.getElementById('status')?.textContent,batch:document.getElementById('batchStatus')?.textContent,saved:document.getElementById('saved')?.textContent})");
    if(state.saved!==previous){previous=state.saved;console.log(state.saved,state.status);}
    if(state.batch?.startsWith('Needs attention:'))throw new Error(state.batch);
    if(state.batch?.startsWith('Batch finished:')){
      const ledger=JSON.parse(readFileSync(resolve(folder,'browser-ledger/checkpoint.json'),'utf8'));
      if(ledger.attempts.length!==protocol.order.length)throw new Error('Incomplete browser ledger');
      const guard=JSON.parse(readFileSync(resolve(folder,'browser-ledger/guard/checkpoint.json'),'utf8'));
      if(guard.length!==ledger.attempts.length)throw new Error('Incomplete frozen guard supplement');
      verifyAll();
      writeFileSync(resolve(folder,'post-run-integrity.json'),JSON.stringify({allFrozenFilesUnchanged:true,files:Object.keys(protocol.frozenFilesSha256).length},null,2));
      const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(resolve(folder,'browser-proof.png'),Buffer.from(shot.data,'base64'));
      writeFileSync(resolve(folder,'browser-console.json'),JSON.stringify(events,null,2));
      console.log('Completed',ledger.attempts.length,'durable browser outcomes; no hardware camera calls.');break;
    }
    await sleep(1000);
  }
  if(!existsSync(resolve(folder,'browser-proof.png')))throw new Error('Browser audit deadline exceeded; previous outcomes remain intact');
}finally{
  writeFileSync(resolve(folder,'browser-console.json'),JSON.stringify(events,null,2));
  try{if(send)await send('Browser.close');}catch{}
  try{ws?.close();}catch{}
  // These handles refer only to the children created above, never other Chrome processes.
  chrome?.kill();server.kill();await sleep(1500);serverLog.end();chromeLog.end();
  const cleanup={};for(const [name,url] of Object.entries({server:site,browser:debug})){try{await fetch(url);cleanup[name]='still responds';}catch{cleanup[name]='no response';}}
  writeFileSync(resolve(folder,'cleanup-receipt.json'),JSON.stringify(cleanup,null,2));
}
