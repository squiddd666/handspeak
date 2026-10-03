"""Audit every catalog entry without training on, or reusing, reserved test clips."""
from pathlib import Path
import csv,json,re,collections
ROOT=Path(__file__).resolve().parents[2]
CAT=json.loads((ROOT/'models/motion-vocabulary.json').read_text())
META=Path('/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits')
tables={s:list(csv.DictReader((META/(s+'.csv')).open())) for s in ['train','val','test']}
normalize=lambda s:re.sub('[^A-Z0-9]','',s.upper())
index=collections.defaultdict(list)
for g in sorted({r['Gloss'] for r in tables['train']}):index[normalize(g)].append(g)
pop=[]
for name in ['development-manifest.json','test-manifest.json']:
 path=Path('/opt/handspeak-training/vocabulary-v7')/name
 if path.exists():pop.extend(json.loads(path.read_text()))
rows=[]
additional=collections.defaultdict(list)
additional_path=ROOT/'reports/vocabulary-expansion/additional-source-candidates.json'
if additional_path.exists():
 for entry in json.loads(additional_path.read_text())['entries']:
  additional[entry['word']].append({k:entry[k] for k in ['dataset','candidateGloss','mapping','metadataClips','signerCounts','videoAvailabilityVerified','semanticMappingVerified']})
for item in CAT['items']:
 candidate=index.get(normalize(item['label']),[])
 # Existing five-word source mappings were already established in that experiment.
 if item['label']=='WANT':candidate=['WANT1','WANT2']
 counts={s:len({r['Participant ID'] for r in table if r['Gloss'] in candidate}) for s,table in tables.items()}
 local=[r for r in pop if r['label']==item['label'] and Path(r['file']).exists()]
 enabled=item['recognition'] in ['default-preview','existing-preview','daily-preview']
 mapped=bool(candidate) and all(counts.values())
 status='enabled-experimental' if enabled else 'candidate-data-needs-validation' if mapped or local else 'needs-verified-training-source'
 baseline_status=status
 if status=='needs-verified-training-source' and additional[item['label']]:status='candidate-data-needs-validation'
 rows.append(dict(id=item['id'],word=item['label'],status=status,citizenCandidateGlosses=candidate,citizenSignerCounts=counts,popSignLocalClips=len(local),sourceVersion=item.get('sourceVersion'),learningVideo=bool(item.get('video') or item.get('youtubeId')),mappingNote='Exact normalized text candidate only; semantic/variant review required before training.' if candidate and not enabled else 'No new mapping approved.',nextStep='Retain current experimental mode.' if enabled else 'Verify sign meaning and source licensing; train on training signers, tune on validation, freeze, and evaluate on untouched test signers plus negative movements.' if status=='candidate-data-needs-validation' else 'Obtain verified labeled movement recordings across separate training, validation, and test signers. Lesson links are not trained models.'))
 rows[-1].update(baselineStatus=baseline_status,additionalSourceCandidates=additional[item['label']])
counts=collections.Counter(r['status'] for r in rows)
report={'catalogEntries':len(rows),'statusCounts':dict(counts),'candidateCitizenEntries':sum(bool(r['citizenCandidateGlosses']) for r in rows),'notes':['Availability is not a recognition-accuracy claim.','Metadata only was inspected for ASL Citizen; no new test video was downloaded or tuned against.','Earlier category models remain withheld after failed evaluation.','Some English phrases need multiple signs and non-manual features; text similarity alone does not verify a mapping.','The full deployed vocabulary has 18 experimental labels, of which 9 appear in this 201-entry catalog.'],'entries':rows}
out=ROOT/'reports/vocabulary-expansion';out.mkdir(exist_ok=True)
(out/'all-201-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'all-201-readiness.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['word','status','candidate_source_glosses','train_signers','validation_signers','test_signers','local_popsign_clips','next_step','additional_dataset_glosses','original_source_status'])
 for r in rows:w.writerow([r['word'],r['status'],' | '.join(r['citizenCandidateGlosses']),*[r['citizenSignerCounts'][s] for s in ['train','val','test']],r['popSignLocalClips'],r['nextStep'],' | '.join(f"{x['dataset']}: {x['candidateGloss']} ({x['mapping']}; unverified)" for x in r['additionalSourceCandidates']),r['baselineStatus']])
missing=[r['word'] for r in rows if r['status']=='needs-verified-training-source']
(out/'README.md').write_text('# All 201 catalog words — readiness audit, 3 October 2026\n\n'+f"{len(rows)} entries checked: {counts['enabled-experimental']} enabled experimental entries, {counts['candidate-data-needs-validation']} additional entries with candidate or locally downloaded data, and {len(missing)} requiring a verified training source.\n\n"+'No new model trained or deployed in this audit. Candidate source glosses require semantic review; source metadata presence is not evidence of recognition. Previously rejected category models remain disabled.\n\n## Missing verified training source\n\n'+', '.join(missing)+'\n\nSee all-201-readiness.csv and all-201-readiness.json for the complete per-entry list.\n')
assert len(rows)==201 and len({r['id'] for r in rows})==201
followups=[]
for name,title in [('completion-status.md','Current completion status'),('fresh-test/README.md','Fresh eight-word test'),('batch1/README.md','First training experiment'),('batch2/README.md','Expanded training experiment'),('batch2-rejection/README.md','Stronger-rejection experiment'),('additional-source-candidates.md','Additional source candidates (metadata only)')]:
 if (out/name).exists():followups.append(f'- [{title}]({name})')
if followups:
 with (out/'README.md').open('a') as f:f.write('\n## Follow-up work\n\n'+'\n'.join(followups)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='entries'},indent=2));print('Missing verified sources:',', '.join(missing))
