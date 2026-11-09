"""Acquire six provenance-screened exact-label test originals; no recognition."""
import argparse,concurrent.futures,datetime,hashlib,json,ssl,tarfile,urllib.request
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.prepare_online_motion_audit import HOST,MAX_CLIP,validate_range,write_new
from scripts.resolve_popsign_v2_provenance import identity
from scripts.prepare_manual_recovery_audit import verified_candidate

def safe_original(member,slug):
    path=PurePosixPath(member)
    if path.is_absolute() or '..' in path.parts or '\\' in member or len(path.parts)!=2 or path.parts[0]!=slug:raise ValueError('Unsafe original member')
    value=identity(path.name)
    if not value or value['recordingKey'][0]!=slug:raise ValueError('Not exact publisher target gloss')
    return path.name

class Fetcher:
    def __init__(self,unverified):self.context=ssl._create_unverified_context() if unverified else ssl.create_default_context()
    def range(self,url,start,end):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.netloc!=HOST or parsed.query or parsed.fragment or parsed.path not in (
            '/data/popsign_v2_1/game/test/baby.tar','/data/popsign_v2_1/game/test/love.tar'):raise ValueError('Only exact public original archives permitted')
        if start<0 or end<start or end-start+1>MAX_CLIP:raise ValueError('Range budget exceeded')
        req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=60,context=self.context) as response:
            if urlsplit(response.url).netloc!=HOST:raise ValueError('Unexpected redirect')
            body=response.read(end-start+2);size=validate_range(response.status,response.headers,body,start,end)
            return body,size,response.headers.get('ETag')

def locate(slug,selected,source_map,fetcher):
    names={r['originalName']:r for r in selected};published=set(source_map['test']['orig_name'].values())
    url=f'https://{HOST}/data/popsign_v2_1/game/test/{slug}.tar';offset=0;total=etag=None;found=[];observed=[]
    for _ in range(200):
        block,size,current=fetcher.range(url,offset,offset+511)
        if total is not None and (size!=total or current!=etag):raise ValueError('Archive changed while locating originals')
        total,etag=size,current
        if block==bytes(512):break
        info=tarfile.TarInfo.frombuf(block,'utf-8','strict');start=offset+512;offset=start+((info.size+511)//512)*512
        if info.size<0 or offset>total:raise ValueError('Invalid original extent')
        if info.isdir():continue
        if not info.isfile():raise ValueError('Unsupported extended/link entry; do not guess original name')
        if not info.name.endswith('.mp4'):continue
        name=safe_original(info.name,slug)
        if name not in published:raise ValueError('Archive absent from source map')
        observed.append(name)
        if name in names:
            if not 0<info.size<=MAX_CLIP:raise ValueError('Original exceeds declared limit')
            found.append(dict(names[name],label=slug.upper(),publisherLabel=slug,publisherSplit='test',source=url,member=info.name,
                byteStart=start,byteSize=info.size,archiveSize=total,archiveETag=etag))
        if len(found)==len(names):break
    if len(found)!=len(names):raise ValueError('Selected exact original missing from bounded archive metadata')
    return dict(slug=slug,selected=found,observed=observed)

def main(args):
    plan_path=args.provenance.resolve();plan=json.loads(plan_path.read_text('utf-8'));verify(plan)
    candidate=args.candidate.resolve();candidate_hash=verified_candidate(candidate)
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    fetcher=Fetcher(args.allow_unverified_publisher_tls)
    url=f'https://{HOST}/view/datasets/popsign_v2_1/index.html'
    with urllib.request.urlopen(url,timeout=60,context=fetcher.context) as response:
        if urlsplit(response.url).netloc!=HOST:raise ValueError('Unexpected license redirect')
        data=response.read(4_000_001)
        if len(data)>4_000_000 or b'CC BY 4.0' not in data:raise ValueError('Publisher version-specific license not verified')
    (out/'publisher-license.html').write_bytes(data)
    registry_path=ROOT.parent/'hs-eval/manual-recovery-audit-20261108/excluded-identity-inventory.json'
    registry=json.loads(registry_path.read_text('utf-8'));known_hashes=set(registry['hashes'])
    for path in (ROOT.parent/'hs-eval').glob('online-motion-audit*/downloads.json'):
        rows=json.loads(path.read_text('utf-8'))
        for row in rows if isinstance(rows,list) else rows.get('downloads',[]):
            if row.get('sha256'):known_hashes.add(row['sha256'])
    frozen={str(plan_path):sha(plan_path),str(candidate/'candidate.json'):candidate_hash,str(out/'publisher-license.html'):sha(out/'publisher-license.html'),
        str(Path(__file__)):sha(Path(__file__)),str(ROOT/'training/test_popsign_v2_acquisition.py'):sha(ROOT/'training/test_popsign_v2_acquisition.py')}
    protocol=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='provenance-screened-exact-label-test-original-acquisition-only',
        frozenFilesSha256=frozen,candidateSha256=candidate_hash,candidatePromotionAllowed=False,
        license='PopSign v2.1 CC BY 4.0',licenseSource=url,sourceMetadata=str(plan_path),selection='Already frozen three metadata-eligible original names each for BABY/LOVE; no decode or prediction based selection.',
        maximumOriginalBytes=6*MAX_CLIP,transportCertificateVerified=not args.allow_unverified_publisher_tls,
        transportLimitation='Host-scoped unverified public publisher TLS; no credentials; local hashes are not publisher-authenticated transport.' if args.allow_unverified_publisher_tls else None,
        trainingAllowed=False,calibrationAllowed=False,predictionsRun=False,newSignerVerified=False,
        scope='Unused-recording candidates under available original-name/timestamp/hash provenance, not a new-signer claim or full-198 audit.')
    write_new(out/'protocol.json',protocol);locations=[];selection_errors=[]
    for slug in ('baby','love'):
        source_path=next(Path(p) for p in plan['frozenFilesSha256'] if p.endswith(slug+'-source-map.json'))
        try:
            row=locate(slug,plan['results'][slug]['selected'],json.loads(source_path.read_text('utf-8')),fetcher);locations.append(row)
            print('Located',slug,len(row['selected']),'frozen original names',flush=True)
        except Exception as error:selection_errors.append(dict(slug=slug,error=str(error)));print('Location failed',slug,str(error),flush=True)
    write_new(out/'frozen-archive-selection.json',dict(selections=locations,errors=selection_errors))
    originals=out/'originals';originals.mkdir();selected=[r for x in locations for r in x['selected']]
    def download(pair):
        i,row=pair;result=dict(row,auditId=f'v2-{i:03}',split='audit-only',auditEligible=False,status='download-failed')
        try:
            data,size,etag=fetcher.range(row['source'],row['byteStart'],row['byteStart']+row['byteSize']-1)
            if size!=row['archiveSize'] or etag!=row['archiveETag']:raise ValueError('Original archive changed after freeze')
            digest=hashlib.sha256(data).hexdigest();path=originals/(result['auditId']+'-'+row['publisherLabel']+'.mp4')
            with path.open('xb') as sink:sink.write(data)
            result.update(path=str(path),sha256=digest,status='downloaded',auditEligible=digest not in known_hashes)
            if not result['auditEligible']:result['exclusionReason']='Known original/derived hash; retained, not described as unused recording'
            print('Downloaded',result['auditId'],len(data),'original bytes',flush=True)
        except Exception as error:result['error']=str(error);print('Download failed',result['auditId'],str(error),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(download,enumerate(selected,1)))
    seen=set()
    for row in results:
        if row.get('sha256') in seen:row.update(auditEligible=False,exclusionReason='Duplicate original inside frozen cohort')
        if row.get('sha256'):seen.add(row['sha256'])
    write_new(out/'downloads.json',results);verify(protocol)
    summary=dict(selected=len(selected),downloaded=sum(r['status']=='downloaded' for r in results),eligibleOriginals=sum(r['auditEligible'] for r in results),
        originalBytes=sum(r['byteSize'] for r in results if r['status']=='downloaded'),metadataLocationErrors=selection_errors,
        predictionsRun=False,decodePending=True,newSignerVerified=False,productionFilesChanged=False)
    write_new(out/'summary.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--allow-unverified-publisher-tls',action='store_true');main(p.parse_args())
