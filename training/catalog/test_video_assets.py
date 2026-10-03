"""Check all library practice clips load and can seek in Chromium; not recognition accuracy."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
base=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8002')
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();page.goto(base,wait_until='domcontentloaded')
 result=page.evaluate('''async()=>{const catalog=await(await fetch('models/motion-vocabulary.json')).json();const reports=[];for(const item of catalog.items.filter(x=>x.video)){const v=document.createElement('video');v.muted=true;v.preload='metadata';v.src=item.video;await new Promise((r,j)=>{v.onloadedmetadata=r;v.onerror=()=>j(Error(item.label));});if(!(v.duration>0&&v.videoWidth>0&&v.videoHeight>0))throw Error(item.label+' invalid metadata');v.currentTime=v.duration/2;await new Promise((r,j)=>{v.onseeked=r;v.onerror=j;});reports.push({label:item.label,duration:v.duration,width:v.videoWidth,height:v.videoHeight});v.removeAttribute('src');v.load();}return reports;}''')
 Path('/opt/handspeak/live-test-results/catalog-video-assets.json').write_text(json.dumps({'clips':result,'allLoadedAndSeeked':True},indent=2));print('Loaded and seeked',len(result),'clips');b.close()
