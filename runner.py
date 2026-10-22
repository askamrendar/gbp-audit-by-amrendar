#!/usr/bin/env python3
"""Local-only browser runner for the public GBP Audit interface."""
import argparse, base64, concurrent.futures, hmac, json, pathlib, secrets, threading, urllib.parse, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import audit
BASE=pathlib.Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(24)
JOBS={}
LOCK=threading.Lock()
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
PORT=8765
ROOT=BASE/'runs'
ALLOWED={'https://askamrendar.github.io'}

from job_support import validate_rows,prepare_payload,package_outputs,files_for,rebuild_reports

def save_job(jid):
 folder=ROOT/jid;folder.mkdir(parents=True,exist_ok=True)
 temporary=folder/'job-state.tmp';temporary.write_text(json.dumps(JOBS[jid]));temporary.replace(folder/'job-state.json')

def recover_jobs():
 if not ROOT.exists():return
 for folder in ROOT.iterdir():
  if not folder.is_dir() or not audit.re.fullmatch('[a-f0-9]{24}',folder.name):continue
  try:
   state=folder/'job-state.json'
   job=json.loads(state.read_text()) if state.is_file() else {'id':folder.name,'messages':['Recovered saved audit outputs'],'status':'completed' if (folder/'audit-results.zip').is_file() else 'failed'}
   if job['status'] in ['queued','running']:job['status']='failed';job.setdefault('messages',[]).append('Runner restarted. Saved data can be used to rebuild reports.')
   job['files']=files_for(folder);JOBS[folder.name]=job
  except (OSError,ValueError,KeyError):continue

def work(jid,rows,media,brand):
 job=JOBS[jid];job['status']='running';folder=ROOT/jid
 try:
  def log(msg):
   with LOCK:job['messages'].append(msg)
  audit.run(rows,folder,BASE/'.audit-browser',media_limit=media,log=log,brand=brand)
  job['files']=package_outputs(folder);job['status']='completed'
 except Exception as e:
  job['status']='failed';job['messages'].append('Audit/export stopped: '+str(e));job['files']=files_for(folder)
 finally:save_job(jid)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def origin_ok(self):
  return self.headers.get('Host')==f'127.0.0.1:{PORT}' and self.headers.get('Origin') in ALLOWED|{f'http://127.0.0.1:{PORT}',None}
 def headers_(self,code,ctype='application/json'):
  self.send_response(code);origin=self.headers.get('Origin')
  if origin in ALLOWED|{f'http://127.0.0.1:{PORT}'}:self.send_header('Access-Control-Allow-Origin',origin)
  self.send_header('Vary','Origin');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Type',ctype)
 def json_(self,code,data):
  self.headers_(code);self.end_headers();self.wfile.write(json.dumps(data).encode())
 def auth(self):
  return self.origin_ok() and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
 def do_OPTIONS(self):
  if not self.origin_ok():return self.json_(403,{'error':'Origin rejected'})
  self.headers_(204);self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Private-Network','true');self.end_headers()
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if path in ['/','/index.html','/app.js','/style.css','/template.csv','/config.js']:
   if self.headers.get('Host')!=f'127.0.0.1:{PORT}':return self.json_(403,{'error':'Host rejected'})
   name='index.html' if path=='/' else path[1:];f=BASE/'docs'/name
   types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.csv':'text/csv'}
   self.headers_(200,types.get(f.suffix,'text/plain'));self.end_headers();self.wfile.write(f.read_bytes());return
  if not self.auth():return self.json_(403,{'error':'Connect using the pairing code shown by your local runner'})
  if path=='/jobs':return self.json_(200,{'jobs':list(JOBS.values())[-20:][::-1]})
  if path=='/health':return self.json_(200,{'name':'GBP Audit by Amrendar','version':'1.3','ready':True})
  parts=path.strip('/').split('/')
  if len(parts)>=2 and parts[0]=='jobs' and parts[1] in JOBS:
   job=JOBS[parts[1]]
   if len(parts)==2:return self.json_(200,job)
   if len(parts)==4 and parts[2]=='file':
    name=urllib.parse.unquote(parts[3]);folder=(ROOT/parts[1]).resolve();f=(folder/name).resolve()
    if folder not in f.parents or not f.is_file() or name not in job.get('files',[]):return self.json_(404,{'error':'Unknown output'})
    mime='application/vnd.openxmlformats-officedocument.presentationml.presentation' if f.suffix=='.pptx' else 'application/zip' if f.suffix=='.zip' else 'application/octet-stream'
    self.headers_(200,mime);self.send_header('Content-Length',str(f.stat().st_size));self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+urllib.parse.quote(f.name));self.end_headers()
    import shutil
    with f.open('rb') as stream:shutil.copyfileobj(stream,self.wfile)
    return
  return self.json_(404,{'error':'Not found'})
 def do_POST(self):
  if not self.auth():return self.json_(403,{'error':'Origin or pairing code rejected'})
  parts=self.path.strip('/').split('/')
  if len(parts)==3 and parts[0]=='jobs' and parts[2]=='export' and parts[1] in JOBS:
   jid=parts[1]
   if any(j['status'] in ['queued','running'] for j in JOBS.values()):return self.json_(409,{'error':'Wait for the active audit to finish'})
   try:
    JOBS[jid]['files']=rebuild_reports(ROOT/jid);JOBS[jid]['status']='completed';JOBS[jid]['messages'].append('Reports rebuilt from saved audit data; Google was not queried again.');save_job(jid);return self.json_(200,JOBS[jid])
   except Exception as exc:return self.json_(400,{'error':'Report rebuild failed: '+str(exc)})
  if self.path!='/jobs':return self.json_(404,{'error':'Not found'})
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=5000000:raise ValueError('Upload must be smaller than 5 MB')
   body=json.loads(self.rfile.read(size))
   with LOCK:
    if any(j['status'] in ['queued','running'] for j in JOBS.values()):raise ValueError('An audit is already running. Wait for it to finish.')
   jid=secrets.token_hex(12);rows,media,brand=prepare_payload(body,ROOT/jid)
   with LOCK:
    if any(j['status'] in ['queued','running'] for j in JOBS.values()):raise ValueError('An audit is already running. Wait for it to finish.')
    JOBS[jid]={'id':jid,'status':'queued','messages':[],'files':[]};save_job(jid);POOL.submit(work,jid,rows,media,brand)
   self.json_(202,{'id':jid})
  except (ValueError,TypeError,KeyError,StopIteration,zipfile.BadZipFile,OSError) as e:self.json_(400,{'error':str(e) or 'Invalid upload'})

def main():
 global PORT
 parser=argparse.ArgumentParser(description=__doc__);args=parser.parse_args()
 recover_jobs()
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 print(f'GBP Audit by Amrendar\nOpen http://127.0.0.1:{PORT}\nPairing code: {TOKEN}\nKeep this window open. Ctrl+C stops the runner. No extension or Google password required.',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.shutdown()
if __name__=='__main__':main()
