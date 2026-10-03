"""Private consistent database snapshots: MariaDB production, SQLite local fallback."""
import gzip,json,os,sqlite3,subprocess
from datetime import datetime,timezone
from pathlib import Path
root=Path(os.environ.get('HANDSPEAK_DATA_DIR','/opt/handspeak/data'));os.umask(0o077)
folder=root/'backups';folder.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
config=os.environ.get('HANDSPEAK_MYSQL_CONFIG')
if config:
 database=json.loads(Path(config).read_text())['database']
 output=folder/('handspeak-'+stamp+'.sql.gz');partial=output.with_suffix('.partial')
 args=['mariadb-dump','--defaults-extra-file='+str(root/'mysql-backup.cnf'),'--single-transaction','--skip-lock-tables','--skip-triggers','--hex-blob','--default-character-set=utf8mb4',database]
 process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with gzip.open(partial,'wb') as out:
   while chunk:=process.stdout.read(1024*1024):out.write(chunk)
  error=process.stderr.read();code=process.wait()
  if code:raise RuntimeError('Database dump failed: '+error.decode(errors='replace'))
  with gzip.open(partial,'rb') as check:
   while check.read(1024*1024):pass
  partial.replace(output)
 except Exception:
  process.kill();process.wait();partial.unlink(missing_ok=True);raise
 extension='*.sql.gz'
else:
 source=root/'handspeak.db'
 if not source.is_file():raise SystemExit('Database not found; backup aborted')
 output=folder/('handspeak-'+stamp+'.db')
 with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(output) as dst:
  src.backup(dst);assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 extension='*.db'
for old in sorted(folder.glob('handspeak-'+extension),reverse=True)[14:]:old.unlink()
print('Database backup verified:',output.name)
