// Owned headless regression browser; never attach to a user's browser/profile.
import {spawn} from 'node:child_process';
import {createWriteStream,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {createHash} from 'node:crypto';
const file=resolve(process.argv[2]),folder=dirname(file),root=process.cwd(),p=JSON.parse(readFileSync(file,'utf8'));
const verify=()=>{for(const [path,digest] of Object.entries(p.frozenFilesSha256))if(createHash('sha256').update(readFileSync(path)).digest('hex')!==digest)throw new Error('Frozen input changed: '+path);};
verify();const site='http://127.0.0.1:8012',debug='http://127.0.0.1:9232';
for(const u of [site,debug]){let used=false;try{const r=await fetch(u,{signal:AbortSignal.timeout(3000)});await r.arrayBuffer();used=true;}catch{}if(used)throw new Error('Refusing existing service '+u);}
const profile=resolve(folder,'headless-profile');if(existsSync(profile))throw new Error('Profile already used; no best-of rerun');mkdirSync(profile);
const serverLog=createWriteStream(resolve(folder,'browser-server.log')),chromeLog=createWriteStream(resolve(folder,'headless-chrome.log'));
const server=spawn(resolve(root,'../hs-eval/.venv/Scripts/python.exe'),['-u','-m','scripts.serve_full198_browser','--protocol',file],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
server.stdout.pipe(serverLog);server.stderr.pipe(serverLog);let serverExit=null;server.once('exit',(code,signal)=>serverExit={code,signal});
let chrome,ws,send,evaluate,events=[];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function ready(url,ms){const end=Date.now()+ms;while(Date.now()<end){if(serverExit)throw new Error('Owned server exited '+JSON.stringify(serverExit));try{const r=await fetch(url);await r.arrayBuffer();if(r.ok)return;}catch{}await sleep(500);}throw new Error('Infrastructure unavailable '+url);}
try{
  await ready(site+'/fixture.html',90000);const checks={};
  for(const [name,url] of Object.entries({beginner:'/api/beginner-asl/status',capstone:'/api/capstone-asl/status'})){
    const r=await fetch(site+url),s=await r.json();if(!r.ok||s.checkpointSha256!==p.productionStatus[name].checkpointSha256)throw new Error('Loaded checkpoint identity mismatch');checks[name]=s.checkpointSha256;
  }
  for(const path of ['/handspeak.db','/api/admin/database-access']){const r=await fetch(site+path);await r.arrayBuffer();if(r.status!==404)throw new Error('Isolation failed '+path);checks[path]=r.status;}
  const blocked=await fetch(site+'/api/beginner-asl',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"consent":true,"frames":[]}'});await blocked.arrayBuffer();if(blocked.status!==403)throw new Error('Unauthorized prediction not blocked');checks.unauthorizedPost=blocked.status;
  writeFileSync(resolve(folder,'infrastructure-checks.json'),JSON.stringify(checks,null,2));
  chrome=spawn(p.chromeExecutable,[`--user-data-dir=${profile}`,'--headless=new','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9232',
    '--disable-quic','--no-first-run','--no-default-browser-check','--autoplay-policy=no-user-gesture-required',
    '--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows',
    '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  chrome.stdout.pipe(chromeLog);chrome.stderr.pipe(chromeLog);await ready(debug+'/json/version',30000);
  const targets=await(await fetch(debug+'/json/list')).json(),page=targets.find(t=>t.type==='page');
  ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  let serial=0;const pending=new Map();ws.addEventListener('message',event=>{
    const d=JSON.parse(event.data);if(d.id&&pending.has(d.id)){const q=pending.get(d.id);pending.delete(d.id);clearTimeout(q.timer);d.error?q.reject(new Error(JSON.stringify(d.error))):q.resolve(d.result);}
    else if(['Runtime.exceptionThrown','Log.entryAdded','Network.loadingFailed'].includes(d.method))events.push(d);
  });
  send=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout '+method));},60000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||'Script failed');return r.result.value;};
  for(const method of ['Runtime.enable','Log.enable','Network.enable','Page.enable'])await send(method);
  await send('Emulation.setDeviceMetricsOverride',{width:1200,height:900,deviceScaleFactor:1,mobile:false});
  writeFileSync(resolve(folder,'browser-version.json'),JSON.stringify(await send('Browser.getVersion'),null,2));
  await send('Page.navigate',{url:site+'/fixture.html#learn'});
  let loaded=false;const boot=Date.now()+180000;
  while(Date.now()<boot){if(serverExit)throw new Error('Owned server exited');
    loaded=await evaluate("Boolean(document.getElementById('vcRun')&&document.getElementById('signExampleListStatus')?.textContent.includes('198 of 198')&&!document.getElementById('expandedWords')?.disabled&&document.getElementById('beginnerStatus')?.textContent.includes('ready')&&document.getElementById('capstoneStatus')?.textContent.includes('ready'))");
    if(loaded)break;await sleep(1000);
  }
  if(!loaded)throw new Error('App/model/198-selector initialization failed before batch');verify();
  await evaluate("document.getElementById('vcRun').click();true");let previous=0;const end=Date.now()+9000000;
  while(Date.now()<end){
    if(serverExit)throw new Error('Owned server exited');
    const s=await evaluate("({status:document.getElementById('vcRunStatus').textContent,count:JSON.parse(document.getElementById('vcReport').textContent).attempts.filter(a=>a.finishedAt).length,summary:document.getElementById('vcSummary').textContent})");
    if(s.count!==previous){previous=s.count;console.log(s.count,s.status);}
    if(s.status.startsWith('Needs attention'))throw new Error(s.status);
    if(s.status.startsWith('Completed')){
      const ledger=JSON.parse(readFileSync(resolve(folder,'browser-ledger/checkpoint.json'),'utf8'));
      if(ledger.attempts.length!==198||ledger.attempts.some((a,i)=>a.id!==p.order[i]))throw new Error('Full-198 ledger incomplete or reordered');
      verify();writeFileSync(resolve(folder,'post-run-integrity.json'),JSON.stringify({allFrozenFilesUnchanged:true,count:Object.keys(p.frozenFilesSha256).length},null,2));
      const screenshot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(resolve(folder,'browser-proof.png'),Buffer.from(screenshot.data,'base64'));
      const exact={matched:ledger.attempts.filter(a=>a.predicted===a.label).length,incorrect:ledger.attempts.filter(a=>a.predicted&&a.predicted!==a.label).length,noMatch:ledger.attempts.filter(a=>!a.predicted).length};
      writeFileSync(resolve(folder,'exact-label-summary.json'),JSON.stringify({references:198,...exact,independentAccuracy:false,source:'previously-used Watch references; synthetic greetings retained'},null,2));console.log('Completed full-198 actual-app reference regression',exact);break;
    }await sleep(1000);
  }
  if(!existsSync(resolve(folder,'browser-proof.png')))throw new Error('Full-198 deadline exceeded; partial ledger retained');
}finally{
  if(evaluate)try{const report=await evaluate("document.getElementById('vcReport')?.textContent");if(report)writeFileSync(resolve(folder,'final-browser-report.json'),report);}catch{}
  writeFileSync(resolve(folder,'browser-console.json'),JSON.stringify(events,null,2));try{if(send)await send('Browser.close');}catch{}try{ws?.close();}catch{}
  chrome?.kill();server.kill();await sleep(1500);serverLog.end();chromeLog.end();
  const cleanup={};for(const [name,url] of Object.entries({server:site,browser:debug})){try{await fetch(url);cleanup[name]='still responds';}catch{cleanup[name]='no response';}}
  writeFileSync(resolve(folder,'cleanup-receipt.json'),JSON.stringify(cleanup,null,2));
}
