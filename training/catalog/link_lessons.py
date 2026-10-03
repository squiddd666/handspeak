"""Verify external ASLU lesson pages; link only, never download/rehost their videos."""
import concurrent.futures,json,re,urllib.request,urllib.error,time
from pathlib import Path
ROOT=Path('/opt/handspeak/repository');WORK=Path('/opt/handspeak-training/vocabulary-v7');cat=json.loads((ROOT/'models/motion-vocabulary.json').read_text())
NUMBERS='https://www.lifeprint.com/asl101/pages-signs/n/numbers.htm'
ALIASES={"You're welcome":['welcome'],"Don't understand":['dont-understand','understand'],"Good morning":['good-morning','goodmorning'],"Good afternoon":['good-afternoon','goodafternoon'],"Good evening":['good-evening','goodevening'],"Excuse me":['excuse','excuse-me'],"Phone":['phone','telephone'],"Shoes":['shoes','shoe'],"Clothes":['clothes','clothing'],"Grandmother":['grandma','grandmother'],"Grandfather":['grandpa','grandfather'],"Don't want":['dont-want','dontwant'],"Don't have":['dont-have'],"Don't touch":['dont-touch'],"Call police":[],"Call ambulance":[],"How many":['how-many','howmany'],"How much":['how-much','howmuch']}
def job(item):
 if 'numbers' in item['categories']:return item['id'],{'url':NUMBERS,'scope':'Numbers lesson, including 0–20, hundreds and thousands','kind':'external-lesson'}
 if item.get('learningUrl'):return item['id'],None
 title=item['label'].title();candidates=ALIASES.get(title,[item['id'],item['id'].replace('-','')]);candidates=list(dict.fromkeys(candidates))
 for name in candidates:
  url=f'https://www.lifeprint.com/asl101/pages-signs/{name[0]}/{name}.htm'
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'HandSpeak educational reference checker'})
   with urllib.request.urlopen(req,timeout=12) as response:body=response.read(250000).decode('utf8',errors='replace');final=response.url
   # Reject redirect-to-home/soft-404 responses; links describe the actual lesson name.
   if 'pages-signs/' not in final or ('404' in body[:1500]) or not re.search(r'<title[^>]*>.*?(ASL|Sign Language)',body,re.I|re.S):continue
   return item['id'],{'url':final,'scope':name.replace('-',' ').upper(),'kind':'external-lesson'}
  except (OSError,ValueError):pass
 return item['id'],None
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=dict(pool.map(job,cat['items']))
(WORK/'external-lessons.json').write_text(json.dumps(results,indent=2));print('Verified external lessons',sum(v is not None for v in results.values()),flush=True)
