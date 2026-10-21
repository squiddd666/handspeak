"""Private, opt-in research inference. No request coordinates are persisted."""
import os,json,math,threading,hashlib,time
from pathlib import Path
LABELS=['NAME','HOME','HAVE','WANT','LOVE']
EXPECTED_SHA='1d9e5ecc1305121c5825b80daade2001ac0c9d44e2d90fb60c4d64615ac4bcab'
class ResearchError(Exception):
 def __init__(self,message,status=422):super().__init__(message);self.status=status

def valid_sequence(seq):
 return (isinstance(seq,list) and len(seq)==20 and all(isinstance(f,list) and len(f)==128 and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<=100 for x in f) and f[0] in (0,1) and f[64] in (0,1) for f in seq))
def prepared(seq,mirror=False):
 result=[]
 for f in seq:
  hands=[]
  for off in ([64,0] if mirror else [0,64]):
   hands.append((f[off],tuple(f[off+1+i]*(-1 if mirror and i%3==0 else .5 if i%3==2 else 1) for i in range(63))))
  result.append(hands)
 return result

def distance(a,b):
 previous=[0]+[float('inf')]*len(b)
 for i,frame in enumerate(a,1):
  current=[float('inf')]*(len(b)+1)
  for j in range(max(1,i-5),min(len(b),i+5)+1):
   cost=0
   for (pa,ha),(pb,hb) in zip(frame,b[j-1]):
    if pa and pb:cost+=math.dist(ha,hb)/math.sqrt(63)
    elif pa!=pb:cost+=2
   current[j]=cost+min(previous[j],current[j-1],previous[j-1])
  previous=current
 return previous[-1]/max(len(a),len(b))

class ResearchWords:
 def __init__(self):self.lock=threading.Lock();self.model=None;self.refs=[];self.compat=[];self.rate_lock=threading.Lock();self.requests={}
 def admit(self,client):
  key=hashlib.sha256(str(client).encode()).hexdigest();now=time.monotonic()
  with self.rate_lock:
   self.requests={k:v for k,v in self.requests.items() if now-v[0]<60}
   start,count=self.requests.get(key,(now,0))
   if count>=12 or (key not in self.requests and len(self.requests)>=4096):raise ResearchError("Recording limit reached. Wait a minute before trying again.",429)
   self.requests[key]=(start,count+1)
 def path(self):return os.environ.get('HANDSPEAK_RESEARCH_WORDS_MODEL','')
 def status(self):return {'available':bool(self.path() and Path(self.path()).is_file()),'labels':LABELS,'experimental':True,'test':{'correct':51,'total':66,'unsupportedFalse':3,'unsupportedTotal':48},'processing':'server-landmarks','retention':'not stored','manualOnly':True}
 def predict(self,seq):
  if not valid_sequence(seq):raise ResearchError('Expected 20 frames of valid hand-landmark features.')
  if not self.lock.acquire(blocking=False):raise ResearchError('The five-word recognizer is busy. Try again shortly.',429)
  try:
   if self.model is None:
    try:
     path=Path(self.path());raw=path.read_bytes()
     if hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA:raise ValueError('Model hash mismatch')
     model=json.loads(raw)
     compatibility=model.get('cameraCompatibility',{})
     if (model['labels']!=LABELS or not all(valid_sequence(r['sequence']) for r in model['samples'])
       or compatibility.get('labels')!=['HOME','HAVE']
       or not all(valid_sequence(r['sequence']) for r in compatibility.get('samples',[]))):raise ValueError('Invalid model')
     self.refs=[(r['label'],prepared(r['sequence'])) for r in model['samples']];self.model=model
     self.compat=[(r['label'],prepared(r['sequence'])) for r in compatibility['samples']]
    except (OSError,ValueError,KeyError,TypeError):raise ResearchError('The five-word model is unavailable.',503)
   a,b=prepared(seq),prepared(seq,True)
   def match(refs,p,allowed):
    ranked=sorted((min(distance(a,r),distance(b,r)),label) for label,r in refs)
    best,label=ranked[0];other=next((d for d,l in ranked if l!=label),float('inf'));ratio=other/(best+1e-6);votes=sum(l==label for _,l in ranked[:3])
    limit=p.get('maxDistanceByLabel',{}).get(label,p['maxDistance'])
    return label if label in allowed and best<=limit and ratio>=p['minRatio'] and (votes>=p['minVotes'] or ratio>=p.get('strongRatio',float('inf'))) else None
   compatibility=self.model['cameraCompatibility'];label=match(self.compat,compatibility['parameters'],compatibility['labels'])
   if label is None:label=match(self.refs,self.model['parameters'],LABELS)
   return {'label':label,'match':'possible' if label else 'no-reliable-match','experimental':True}
  finally:self.lock.release()
research_words=ResearchWords()
