"""One-time, transactional SQLite -> empty MariaDB import with row verification.
Run as the server owner with the website stopped. Does not delete the source database.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
import pymysql
TABLES=['users','gestures','sessions','detections','evaluations','auth_sessions','password_resets']
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--database',default='handspeak');p.add_argument('--report',type=Path,required=True);args=p.parse_args()
if args.database not in {'handspeak','handspeak_test','handspeak_migration_test'}:raise SystemExit('Unexpected destination database')
if not args.source.is_file():raise SystemExit('Source database does not exist')
source=sqlite3.connect(f'file:{args.source}?mode=ro',uri=True);source.row_factory=sqlite3.Row
if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Source integrity check failed')
data={t:[dict(r) for r in source.execute('SELECT * FROM '+t)] for t in TABLES};users={r['id'] for r in data['users']}
for row in data['sessions']:
 uid=row.get('owner_id','').removeprefix('user:') if row.get('owner_id','').startswith('user:') else None
 row['user_id']=uid if uid in users else None
source.close();dest=pymysql.connect(unix_socket='/run/mysqld/mysqld.sock',user='root',database=args.database,charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor)
report={'source':'SQLite','destination':'MariaDB','tables':{},'sourceRetained':True}
try:
 with dest.cursor() as c:
  for table in TABLES:
   c.execute('SELECT COUNT(*) n FROM '+table)
   if c.fetchone()['n']:raise RuntimeError('Destination must be empty: '+table)
  for table,rows in data.items():
   if rows:
    columns=list(rows[0]);sql='INSERT INTO '+table+' ('+','.join('`'+k+'`' for k in columns)+') VALUES('+','.join(['%s']*len(columns))+')'
    c.executemany(sql,[[row[k] for k in columns] for row in rows])
   c.execute('SELECT * FROM '+table);actual=c.fetchall()
   canonical=lambda rs: sorted(json.dumps(r,sort_keys=True,separators=(',',':')) for r in rs)
   if canonical(rows)!=canonical(actual):raise RuntimeError('Row comparison failed: '+table)
   report['tables'][table]={'rows':len(rows),'exactMatch':True,'sha256':hashlib.sha256(json.dumps(canonical(rows)).encode()).hexdigest()}
 dest.commit()
except Exception:
 dest.rollback();raise
finally:dest.close()
args.report.write_text(json.dumps(report,indent=2));print(json.dumps({t:v['rows'] for t,v in report['tables'].items()}))
