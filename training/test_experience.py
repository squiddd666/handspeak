"""Practice upload checks use only temporary files and SQLite."""
import io,json,sqlite3,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
from experience import ExperienceStore,SQLITE_SCHEMA
class Invalid(Exception):
 def __init__(self,status,message):self.status=status;super().__init__(message)
class UploadTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'models').mkdir();(self.root/'media/signs').mkdir(parents=True)
  (self.root/'models/motion-vocabulary.json').write_text(json.dumps({'items':[]}));self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;self.db.executescript(SQLITE_SCHEMA)
  @contextmanager
  def connect():
   with self.db:yield self.db
  self.store=ExperienceStore(connect,self.root,Invalid,lambda:'2026-10-11T00:00:00+00:00')
 def tearDown(self):self.db.close();self.temp.cleanup()
 def test_readable_video_is_assigned_and_preserves_description(self):
  self.store.save({'id':'hello','description':'Practice slowly','hidden':True})
  data=(Path(__file__).resolve().parents[1]/'media/signs/hello.mp4').read_bytes()
  result=self.store.upload(io.BytesIO(data),len(data),'hello','video/mp4')
  self.assertEqual((self.root/result['video']).read_bytes(),data);settings=self.store.settings()['items']['hello'];self.assertTrue(settings['hidden']);self.assertEqual(settings['description'],'Practice slowly');self.assertEqual(settings['video'],result['video'])
 def test_invalid_and_interrupted_uploads_leave_no_files(self):
  for data,length,word,mime in [(b'x'*32,32,'hello','video/mp4'),(b'x',32,'hello','video/mp4'),(b'x'*32,32,'../hello','video/mp4'),(b'x'*32,32,'hello','text/html')]:
   with self.assertRaises(Invalid):self.store.upload(io.BytesIO(data),length,word,mime)
  self.assertEqual(list((self.root/'media/signs').iterdir()),[])
if __name__=='__main__':unittest.main()
