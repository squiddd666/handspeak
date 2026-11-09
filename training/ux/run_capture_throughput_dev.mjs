// Own fresh headless browser and loopback server; never the user's browser.
import {spawn} from 'node:child_process';
import {createWriteStream,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {createHash} from 'node:crypto';
const config=resolve(process.argv[2]),folder=dirname(config),root=process.cwd();
const frozen=JSON.parse(readFileSync(config,'utf8'));
const verify=()=>{for(const [path,digest] of Object.entries({...frozen.filesSha256,...frozen.modelAndGateSha256}))
  if(createHash('sha256').update(readFileSync(path)).digest('hex')!==digest)throw new Error('Development input changed: '+path);};
verify();
const profile=resolve(folder,'profile');if(existsSync(profile))throw new Error('Development run profile already exists');mkdirSync(profile);
const site='http://127.0.0.1:8010',debug='http://127.0.0.1:9230',sleep=ms=>new Promise(r=>setTimeout(r,ms));
for(const url of [site,debug]){let occupied=false;try{const r=await fetch(url);await r.arrayBuffer();occupied=true;}catch{}if(occupied)throw new Error('Owned port occupied: '+url);}
const logs=['server.log','chrome.log'].map(n=>createWriteStream(resolve(folder,n)));
const server=spawn(resolve(root,'../hs-eval/.venv/Scripts/python.exe'),['-u','-m','scripts.serve_capture_throughput_dev','--config',config],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});server.stdout.pipe(logs[0]);server.stderr.pipe(logs[0]);
let chrome,ws,send,events=[];
async function ready(url){for(let i=0;i<120;i++){try{const r=await fetch(url);await r.arrayBuffer();if(r.ok)return;}catch{}await sleep(500);}throw new Error('Service did not start: '+url);}
try{
  await ready(site+'/fixture.html');
  chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[`--user-data-dir=${profile}`,'--headless=new','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9230','--disable-quic','--no-first-run','--no-default-browser-check','--autoplay-policy=no-user-gesture-required','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});chrome.stdout.pipe(logs[1]);chrome.stderr.pipe(logs[1]);
  await ready(debug+'/json/version');const pages=await (await fetch(debug+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  let serial=0;const pending=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}}else if(['Runtime.exceptionThrown','Log.entryAdded','Network.loadingFailed'].includes(m.method))events.push(m);});
  send=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},60000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||'Fixture failed');return r.result.value;};
  await send('Runtime.enable');await send('Log.enable');await send('Network.enable');await send('Page.enable');
  writeFileSync(resolve(folder,'browser-version.json'),JSON.stringify(await send('Browser.getVersion'),null,2));
  await send('Page.navigate',{url:site+'/fixture.html'});
  for(let i=0;i<60&&!await evaluate('window.devReady===true');i++)await sleep(500);
  if(!await evaluate('window.devReady===true'))throw new Error('Development module failed to load');
  await evaluate('void window.runDev();true');let count=-1,done=false;
  const end=Date.now()+900000;
  while(Date.now()<end){const state=await evaluate('window.devState');
    if(state.results.length!==count){count=state.results.length;writeFileSync(resolve(folder,'checkpoint.json'),JSON.stringify(state,null,2));console.log('Development cases saved:',count);}
    if(state.done){done=true;writeFileSync(resolve(folder,'result.json'),JSON.stringify(state,null,2));if(state.error)throw new Error(state.error);break;}
    await sleep(1000);
  }
  if(!done)throw new Error('Development deadline exceeded');
  verify();
  const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(resolve(folder,'proof.png'),Buffer.from(shot.data,'base64'));
  console.log('Development probe completed; hardware calls: 0.');
}finally{
  writeFileSync(resolve(folder,'console.json'),JSON.stringify(events,null,2));
  try{if(send)await send('Browser.close');}catch{}try{ws?.close();}catch{}chrome?.kill();server.kill();logs.forEach(s=>s.end());
}
