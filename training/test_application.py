"""HTTP-level account, data-isolation, migration, and input-validation regression checks."""
import importlib.util,json,threading,tempfile,unittest,urllib.request,urllib.error,http.cookiejar,sqlite3
from pathlib import Path
spec=importlib.util.spec_from_file_location('handspeak_server',Path(__file__).resolve().parents[1]/'server.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
PASSWORD='correct horse test battery'
class Client:
 def __init__(self,base):
  self.base=base;self.jar=http.cookiejar.CookieJar();self.open=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar)).open
 def call(self,path,data=None,method=None,headers=None):
  h={'Content-Type':'application/json',**(headers or {})};req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=h)
  try:r=self.open(req)
  except urllib.error.HTTPError as e:r=e
  body=r.read();return r.code,(json.loads(body) if 'application/json' in r.headers.get('Content-Type','') else body.decode('utf8',errors='replace')),r.headers
class ApplicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if app.MYSQL_CONFIG:
   config=json.loads(Path(app.MYSQL_CONFIG).read_text())
   if config.get("database") != "handspeak_test":raise RuntimeError("Destructive application tests require the isolated handspeak_test database")
  cls.temp=tempfile.TemporaryDirectory();app.DB_PATH=Path(cls.temp.name)/'handspeak.db';app.ADMIN_SETUP_PATH=Path(cls.temp.name)/'admin-setup-token';app.initialize_database();app.HandSpeakHandler.log_message=lambda *args:None
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.HandSpeakHandler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def setUp(self):
  with app.connect() as db:
   for table in ['password_resets','auth_sessions','detections','sessions','users','evaluations']:db.execute('DELETE FROM '+table)
  app.AUTH_ATTEMPTS.clear();app.ADMIN_SETUP_PATH.write_text('private-setup-test-token');self.a=Client(self.base);self.b=Client(self.base)
 def register(self,c,email='user@example.test'):
  result=c.call('/api/auth/register',{'email':email,'password':PASSWORD,'role':'admin'});self.assertEqual(result[0],201,result);return c.call('/api/auth/me')[1]['user']
 def admin(self):
  self.assertEqual(self.a.call('/api/auth/setup',{'email':'admin@example.test','password':PASSWORD,'token':'private-setup-test-token'})[0],201)
 def save(self,c,message='HELLO'):
  result=c.call('/api/sessions',{'message':message,'durationMs':10,'detections':[]});self.assertEqual(result[0],201,result);return result[1]['id']
 def test_word_preview_is_public_but_requires_consent(self):
  self.assertEqual(self.a.call('/api/research-words/status')[0],200)
  self.assertEqual(self.a.call('/api/research-words',{'consent':True,'sequence':[]})[0],422)
  self.register(self.b);self.assertEqual(self.b.call('/api/research-words/status')[0],200)
  self.admin();self.assertEqual(self.a.call('/api/research-words/status')[0],200)
  self.assertEqual(self.a.call('/api/research-words',{'sequence':[]})[0],422)
  self.assertEqual(self.a.call('/api/research-words',{'consent':True,'sequence':[]})[0],422)
  self.assertEqual(self.a.call('/api/research-words',{'consent':True,'sequence':[]},headers={'Origin':'https://evil.example'})[0],403)
 def test_registration_login_logout_and_no_role_escalation(self):
  user=self.register(self.a);self.assertEqual(user['role'],'user');self.assertEqual(self.a.call('/api/admin/overview')[0],403)
  self.assertEqual(self.a.call('/api/auth/logout',{})[0],200);self.assertIsNone(self.a.call('/api/auth/me')[1]['user'])
  self.assertEqual(self.a.call('/api/auth/login',{'email':user['email'],'password':'bad'})[0],401)
  self.assertEqual(self.a.call('/api/auth/login',{'email':user['email'],'password':PASSWORD})[0],200)
 def test_guest_and_account_history_isolation(self):
  sid=self.save(self.a,'private A');self.assertEqual(self.b.call('/api/sessions')[1]['sessions'],[])
  user=self.register(self.a);self.assertEqual(len(self.a.call('/api/sessions')[1]['sessions']),1)
  self.assertEqual(self.b.call('/api/sessions/'+sid,method='DELETE')[0],404)
  self.assertNotIn('private A',self.b.call('/api/export/sessions.csv')[1])
  # Public user IDs must never be usable as anonymous ownership credentials.
  self.assertEqual(Client(self.base).call('/api/sessions',headers={'Cookie':'handspeak_visitor='+user['id']})[1]['sessions'],[])
  self.assertEqual(self.a.call('/api/sessions/'+sid,method='DELETE')[0],200)
  self.assertEqual(self.a.call('/api/metrics')[1]['sessions'],0)
 def test_account_history_across_devices(self):
  self.register(self.a);self.save(self.a)
  self.b.call('/api/auth/login',{'email':'user@example.test','password':PASSWORD})
  self.assertEqual(len(self.b.call('/api/sessions')[1]['sessions']),1)
 def test_admin_setup_is_private_and_single_use(self):
  self.assertEqual(self.a.call('/api/auth/setup',{'email':'a@example.test','password':PASSWORD,'token':'bad'})[0],403)
  self.admin();self.assertEqual(self.a.call('/api/admin/overview')[0],200);self.assertFalse(app.ADMIN_SETUP_PATH.exists())
  self.assertEqual(self.b.call('/api/auth/setup',{'email':'b@example.test','password':PASSWORD,'token':'private-setup-test-token'})[0],403)
 def test_reset_single_use_and_revokes_sessions(self):
  self.admin();user=self.register(self.b);token=self.a.call('/api/admin/reset-link',{'userId':user['id']})[1]['token'];c=Client(self.base)
  self.assertEqual(c.call('/api/auth/reset',{'token':token,'password':'a different long password'})[0],200)
  self.assertIsNone(self.b.call('/api/auth/me')[1]['user'])
  self.assertEqual(c.call('/api/auth/reset',{'token':token,'password':PASSWORD})[0],403)
 def test_deactivate_revokes_access(self):
  self.admin();user=self.register(self.b);self.assertEqual(self.a.call('/api/admin/user-status',{'userId':user['id'],'active':False})[0],200)
  self.assertIsNone(self.b.call('/api/auth/me')[1]['user']);self.assertEqual(self.b.call('/api/auth/login',{'email':user['email'],'password':PASSWORD})[0],401)
  own=self.a.call('/api/auth/me')[1]['user'];self.assertEqual(self.a.call('/api/admin/user-status',{'userId':own['id'],'active':False})[0],422)
 def test_password_change_checks_current_and_revokes_other_device(self):
  self.register(self.a);self.b.call('/api/auth/login',{'email':'user@example.test','password':PASSWORD})
  self.assertEqual(self.a.call('/api/auth/password',{'currentPassword':'bad','password':'replacement password here'})[0],403)
  self.assertEqual(self.a.call('/api/auth/password',{'currentPassword':PASSWORD,'password':'replacement password here'})[0],200)
  self.assertIsNone(self.b.call('/api/auth/me')[1]['user']);self.assertIsNotNone(self.a.call('/api/auth/me')[1]['user'])
 def test_private_static_files_head_and_get_blocked(self):
  for path in ['/server.py','/handspeak.db','/training/','/.git/config','/admin-setup-token','/models/']:
   for method in ['GET','HEAD']:self.assertEqual(self.a.call(path,method=method)[0],404,(path,method))
  self.assertEqual(self.a.call('/index.html')[0],200);self.assertEqual(self.a.call('/models/asl-words.json')[0],200)
 def test_invalid_session_inputs_return_json(self):
  for value in ['bad',None,True,float('nan'),float('inf'),-1,10**400]:
   result=self.a.call('/api/sessions',{'message':'X','durationMs':value});self.assertEqual(result[0],422,result)
  self.assertEqual(self.a.call('/api/sessions',{'message':None})[0],422)
 def test_csv_formula_and_cross_origin(self):
  self.save(self.a,'=1+1');self.assertIn("'=1+1",self.a.call('/api/export/sessions.csv')[1])
  self.assertEqual(self.a.call('/api/auth/register',{'email':'x@example.test','password':PASSWORD},headers={'Origin':'https://evil.invalid'})[0],403)
 def test_cookie_flags_and_storage(self):
  result=self.a.call('/api/auth/register',{'email':'user@example.test','password':PASSWORD},headers={'X-Forwarded-Proto':'https'})
  cookies=' '.join(result[2].get_all('Set-Cookie'));self.assertIn('HttpOnly',cookies);self.assertIn('Secure',cookies);self.assertIn('SameSite=Lax',cookies)
  with app.connect() as db:
   self.assertNotIn(PASSWORD,db.execute('SELECT password_hash FROM users').fetchone()[0]);self.assertEqual(len(db.execute('SELECT token_hash FROM auth_sessions').fetchone()[0]),64)
 def test_admin_database_gate_search_and_feedback_export(self):
  self.assertEqual(self.b.call('/api/admin/database-access')[0],401)
  self.admin();self.assertEqual(self.a.call('/api/admin/database-access')[0],200)
  user=self.register(self.b)
  self.assertEqual(self.b.call('/api/admin/database-access')[0],403)
  self.assertEqual(self.a.call('/api/admin/overview?q=not-present')[1]['users'],[])
  self.assertEqual(len(self.a.call('/api/admin/overview?q=user%40')[1]['users']),1)
  self.assertEqual(self.b.call('/api/evaluations',{'respondentType':'Student','accuracy':3,'usability':4,'performance':5,'comments':'=2+2'})[0],201)
  self.assertEqual(self.b.call('/api/admin/export/evaluations.csv')[0],403)
  self.assertIn("'=2+2",self.a.call('/api/admin/export/evaluations.csv')[1])
 def test_interpretation_status_validation_and_origin(self):
  status=self.a.call('/api/interpret/status');self.assertEqual(status[0],200);self.assertTrue(status[1]['local'])
  self.assertEqual(self.a.call('/api/interpret',{'text':''})[0],422)
  self.assertEqual(self.a.call('/api/interpret',{'text':'HELLO'},headers={'Origin':'https://evil.invalid'})[0],403)
  self.assertEqual(self.a.call('/interpretation.py')[0],404)
 def test_throttling(self):
  for _ in range(20):self.a.call('/api/auth/login',{'email':'bad','password':'x'})
  self.assertEqual(self.a.call('/api/auth/login',{'email':'bad','password':'x'})[0],429)
 def test_legacy_records_are_not_claimed(self):
  with app.connect() as db:db.execute("INSERT INTO sessions(id,message,character_count,duration_ms,created_at,owner_id) VALUES('legacy','preserved',9,0,'2026-01-01','')")
  self.register(self.a);self.assertEqual(self.a.call('/api/sessions')[1]['sessions'],[])
  with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],1)
if __name__=='__main__':unittest.main()
