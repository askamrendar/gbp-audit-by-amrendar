import base64,io,json,pathlib,secrets,sys,tempfile,time,unittest,zipfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
try:
 import service
 from fastapi.testclient import TestClient
 SERVICE=True
except ImportError:SERVICE=False
from job_support import package_outputs,rebuild_reports
from report import export_ppt

def sample():return {'input':{'store_code':'A','maps_url':'https://www.google.com/maps?cid=123','keyword':'shoe'},'started_at':'2026-10-22','profiles':[{'name':'Example','checks':[]}],'ranking':{}}

class ExportTests(unittest.TestCase):
 def test_corrupt_ppt_is_not_advertised(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=pathlib.Path(tmp);(folder/'broken.pptx').write_bytes(b'broken')
   with self.assertRaises(zipfile.BadZipFile):package_outputs(folder)
 def test_rebuild_and_archive_exclude_job_credentials(self):
  from pptx import Presentation
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);store=root/'store';store.mkdir();(store/'audit.json').write_text(json.dumps(sample()));(root/'job-state.json').write_text('{"owner":"private"}')
   files=rebuild_reports(root);self.assertIn('store/audit-draft.pptx',files);self.assertNotIn('job-state.json',files)
   self.assertEqual(len(Presentation(store/'audit-draft.pptx').slides),7)
   with zipfile.ZipFile(root/'audit-results.zip') as archive:self.assertNotIn('job-state.json',archive.namelist());self.assertIsNone(archive.testzip())

@unittest.skipUnless(SERVICE,'Install requirements-service.txt for hosted tests')
class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.patch=patch.object(service,'ROOT',self.root);self.patch.start();service.JOBS.clear();service.ATTEMPTS.clear();self.client=TestClient(service.app);self.client.__enter__();self.token=self.client.post('/api/session').json()['token'];self.headers={'Authorization':'Bearer '+self.token}
 def tearDown(self):
  self.client.__exit__(None,None,None);self.patch.stop();self.tmp.cleanup()
 def body(self):return {'consent':True,'rows':[sample()['input']]}
 def stored(self,who=None):
  jid=secrets.token_hex(12);folder=self.root/jid;folder.mkdir();p=folder/'A';p.mkdir();(p/'audit.json').write_text(json.dumps(sample()));files=rebuild_reports(folder)
  service.JOBS[jid]={'id':jid,'owner':who or service.hashlib.sha256(self.token.encode()).hexdigest(),'created_at':time.time(),'status':'completed','messages':[],'files':files};service.persist(service.JOBS[jid]);return jid
 def test_auto_session_and_config(self):
  self.assertEqual(len(self.token),43);self.assertIn('"hosted": true',self.client.get('/config.js').text);self.assertEqual(self.client.get('/api/health').json()['mode'],'hosted')
 def test_origin_and_auth(self):
  self.assertEqual(self.client.get('/api/jobs').status_code,401);self.assertEqual(self.client.post('/api/session',headers={'Origin':'https://evil.test'}).status_code,403)
 def test_private_history_and_cross_session_download(self):
  jid=self.stored();other={'Authorization':'Bearer '+secrets.token_urlsafe(32)}
  self.assertEqual(len(self.client.get('/api/jobs',headers=self.headers).json()['jobs']),1)
  self.assertEqual(self.client.get('/api/jobs',headers=other).json()['jobs'],[])
  self.assertEqual(self.client.get(f'/api/jobs/{jid}/file/A/audit-draft.pptx',headers=other).status_code,404)
  response=self.client.get(f'/api/jobs/{jid}/file/A/audit-draft.pptx',headers=self.headers);self.assertEqual(response.content[:2],b'PK');self.assertIn('attachment',response.headers['content-disposition'])
  self.assertEqual(self.client.get(f'/api/jobs/{jid}/file/A%2F..%2Fjob-state.json',headers=self.headers).status_code,404)
 def test_collection_queue_passes_headless_options(self):
  with patch.object(service.POOL,'submit') as submit:
   r=self.client.post('/api/jobs',headers=self.headers,json=self.body());self.assertEqual(r.status_code,202)
   args=submit.call_args.args;self.assertEqual(args[1],r.json()['id'])
   self.assertEqual(self.client.post('/api/jobs',headers=self.headers,json=self.body()).status_code,409)
  jid=r.json()['id']
  def fake(rows,out,browser,**kw):
   self.assertTrue(kw['headless']);self.assertEqual(kw['channel'],'chromium');(out/'A').mkdir(parents=True,exist_ok=True);(out/'A/audit.json').write_text(json.dumps(sample()));export_ppt(sample(),out/'A/audit-draft.pptx')
  with patch.object(service.audit,'run',side_effect=fake):service.work(jid,[sample()['input']],10,{})
  self.assertEqual(service.JOBS[jid]['status'],'completed');self.assertIn('audit-results.zip',service.JOBS[jid]['files'])
 def test_consent_limits_and_corrupt_upload(self):
  body=self.body();body['consent']=False;self.assertEqual(self.client.post('/api/jobs',headers=self.headers,json=body).status_code,400)
  body=self.body();body['rows']*=11;self.assertEqual(self.client.post('/api/jobs',headers=self.headers,json=body).status_code,400)
  self.assertEqual(self.client.post('/api/jobs',headers=self.headers,json={'consent':True,'file':base64.b64encode(b'broken').decode(),'extension':'xlsx'}).status_code,400)
 def test_export_requeues_saved_data_only(self):
  jid=self.stored()
  with patch.object(service.POOL,'submit') as submit:
   r=self.client.post(f'/api/jobs/{jid}/export',headers=self.headers);self.assertEqual(r.status_code,200);self.assertTrue(submit.call_args.args[-1])
  with patch.object(service.audit,'run') as collect:service.work(jid,[],0,{},True);collect.assert_not_called()
  self.assertEqual(service.JOBS[jid]['status'],'completed')
 def test_recover_and_expire(self):
  jid=self.stored();service.JOBS[jid]['status']='running';service.persist(service.JOBS[jid]);service.JOBS.clear();service.load_jobs();self.assertEqual(service.JOBS[jid]['status'],'failed')
  service.JOBS[jid]['created_at']=time.time()-service.TTL-1;service.cleanup();self.assertNotIn(jid,service.JOBS);self.assertFalse((self.root/jid).exists())
 def test_global_queue_limit(self):
  with patch.object(service.POOL,'submit'):
   for n in range(4):
    h={'Authorization':'Bearer '+secrets.token_urlsafe(32)};self.assertEqual(self.client.post('/api/jobs',headers=h,json=self.body()).status_code,202)
   self.assertEqual(self.client.post('/api/jobs',headers=self.headers,json=self.body()).status_code,429)

if __name__=='__main__':unittest.main()
