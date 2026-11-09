"""Inspect exact BABY/LOVE publisher labels; never decode or predict a video."""
import argparse,datetime,hashlib,json,re,ssl,urllib.request
from pathlib import Path
from scripts.run_online_native_audit import ROOT
from scripts.prepare_online_motion_audit import HOST,write_new


def parse_source_map(html,slug):
    # Parse DATA only, never execute publisher JavaScript. Exact dataset/word
    # declarations prevent a related word/compound from being silently aliased.
    if f'sign="{slug}",ds="popsign_v2_1",dsCategory="game"' not in html:
        raise ValueError('Wrong exact publisher dataset/gloss')
    marker='sourceMap=JSON.parse(';start=html.index(marker)+len(marker)
    quote=html[start]
    if quote not in ('"',"'"):raise ValueError('Quoted data literal required')
    start+=1;end=start;escaped=False
    while end<len(html):
        char=html[end]
        if char==quote and not escaped:break
        escaped=not escaped if char=='\\' else False
        end+=1
    if end==len(html) or not html[end+1:].lstrip().startswith(')'):raise ValueError('Unterminated metadata literal')
    literal=html[start:end]
    # Current publisher single-quoted literals contain strict JSON data. Do
    # not execute JS or assume a particular semicolon/comma after JSON.parse.
    if quote=='"':literal=json.loads('"'+literal+'"')
    value=json.loads(literal)
    if not isinstance(value,dict) or not {'train','val','test'}<=set(value):raise ValueError('Missing official split metadata')
    for split in ('train','val','test'):
        fields=value[split]
        if not isinstance(fields,dict) or not isinstance(fields.get('orig_name'),dict):raise ValueError('Missing original source linkage')
        if not all(isinstance(n,str) and n.endswith('.mp4') for n in fields['orig_name'].values()):raise ValueError('Invalid source identity')
    return value


def main(args):
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    context=ssl._create_unverified_context() if args.allow_unverified_publisher_tls else ssl.create_default_context()
    protocol=dict(purpose='publisher-metadata-discovery-only',frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        requestedExactLabels=['BABY','LOVE'],dataset='popsign_v2_1',recordingSelection=False,videosDownloaded=False,predictionsRun=False,
        trainingAllowed=False,calibrationAllowed=False,newSignerClaim=False,
        transportCertificateVerified=not args.allow_unverified_publisher_tls,
        transportLimitation='Public publisher TLS chain validation unavailable on this host; explicitly host-scoped unverified TLS, no credentials.' if args.allow_unverified_publisher_tls else None,
        labelPolicy='Only literal publisher BABY and LOVE labels. PETSNAME/WANTTO/HURT are not silently substituted for NAME/WANT/PAIN.',
        auditRequirement='Before using v2 recordings, resolve original/previous filenames to prior recording identities; re-anonymization is not new data.')
    write_new(out/'protocol.json',protocol);summary={}
    for slug in ('baby','love'):
        url=f'https://{HOST}/view/datasets/popsign_v2_1/game/{slug}/index.html'
        try:
            with urllib.request.urlopen(url,timeout=60,context=context) as response:
                if not response.url.startswith(f'https://{HOST}/'):raise ValueError('Unexpected publisher redirect')
                data=response.read(4_000_001)
                if len(data)>4_000_000:raise ValueError('Metadata exceeds bound')
            (out/(slug+'.html')).write_bytes(data);source=parse_source_map(data.decode('utf-8'),slug);write_new(out/(slug+'-source-map.json'),source)
            names=list(source['test']['orig_name'].values());patterns=sorted({n.split('.',1)[0] for n in names})
            summary[slug]=dict(counts={s:len(source[s]['orig_name']) for s in ('train','val','test')},sourcePrefixes=patterns,
                htmlSha256=hashlib.sha256(data).hexdigest(),url=url,videoDownloaded=False,recordingNewVerified=False)
            print(slug,json.dumps(summary[slug]),flush=True)
        except Exception as error:
            summary[slug]=dict(error=str(error),videoDownloaded=False,recordingNewVerified=False);print(slug,'metadata unavailable:',error,flush=True)
    write_new(out/'metadata-summary.json',summary)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-unverified-publisher-tls',action='store_true');main(p.parse_args())
