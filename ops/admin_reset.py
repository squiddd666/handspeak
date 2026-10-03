"""Server-owner recovery for an existing administrator; never serves a reset token publicly."""
import argparse,hashlib,os,secrets,sqlite3,time,json
from pathlib import Path
p=argparse.ArgumentParser(description='Issue a 30-minute single-use recovery link for an existing administrator. Run privately on the server.')
p.add_argument('email');p.add_argument('--base-url',default='https://handspeak.cvsu.dev');args=p.parse_args()
root=Path(os.environ.get('HANDSPEAK_DATA_DIR','/opt/handspeak/data'))
config=Path(os.environ.get('HANDSPEAK_MYSQL_CONFIG',str(root/'mysql.json')))
if config.is_file():
 import pymysql
 connection=pymysql.connect(**json.loads(config.read_text()),charset='utf8mb4')
 db=connection.cursor(); placeholder='%s'
else:
 path=root/'handspeak.db'
 if not path.is_file():raise SystemExit('Database not found')
 connection=sqlite3.connect(path);db=connection.cursor();placeholder='?'
try:
 db.execute("SELECT id FROM users WHERE email="+placeholder+" AND role='admin' AND active=1",(args.email.strip().lower(),));row=db.fetchone()
 if not row:raise SystemExit('No active administrator with this email')
 token=secrets.token_urlsafe(32)
 db.execute('DELETE FROM password_resets WHERE user_id='+placeholder,(row[0],))
 db.execute('INSERT INTO password_resets VALUES('+','.join([placeholder]*3)+')',(hashlib.sha256(token.encode()).hexdigest(),row[0],time.time()+1800))
 connection.commit()
finally:connection.close()
print('Keep this single-use link private; it expires in 30 minutes:')
print(args.base_url.rstrip('/')+'/#reset='+token)
