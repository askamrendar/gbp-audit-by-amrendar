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

def validate_rows(rows):
 if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Supply 1–100 stores per run')
 for row in rows:
  if not isinstance(row,dict):raise ValueError('Each store must be a record')
  if not audit.re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(row.get('store_code',''))):raise ValueError('Store code: use letters, numbers, hyphens or underscores')
  audit.maps_url(str(row.get('maps_url','')))
  if not 1<=len(str(row.get('keyword','')).strip())<=200:raise ValueError('A keyword is required (up to 200 characters)')
  if bool(str(row.get('search_latitude') or '').strip())!=bool(str(row.get('search_longitude') or '').strip()):raise ValueError('Supply both search coordinates together')
  for key,lo,hi in [('search_latitude',-90,90),('search_longitude',-180,180)]:
   if row.get(key) not in [None,''] and not lo<=float(row[key])<=hi:raise ValueError('Invalid search coordinates')
 return rows

def work(jid,rows,media,brand):
 job=JOBS[jid];job['status']='running';folder=ROOT/jid
 try:
  def log(msg):
   with LOCK:job['messages'].append(msg)
  audit.run(rows,folder,BASE/'.audit-browser',media_limit=media,log=log,brand=brand)
  archive=folder/'audit-results.zip'
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for f in folder.rglob('*'):
    if f.is_file() and f!=archive:z.write(f,f.relative_to(folder))
  job['files']=[str(f.relative_to(folder)) for f in folder.rglob('*') if f.is_file() and f.suffix in ['.pptx','.zip','.csv','.json']]
  job['status']='completed'
 except Exception as e:job['status']='failed';job['messages'].append(str(e))

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
  if path in ['/','/index.html','/app.js','/style.css','/template.csv']:
   if self.headers.get('Host')!=f'127.0.0.1:{PORT}':return self.json_(403,{'error':'Host rejected'})
   name='index.html' if path=='/' else path[1:];f=BASE/'docs'/name
   types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.csv':'text/csv'}
   self.headers_(200,types.get(f.suffix,'text/plain'));self.end_headers();self.wfile.write(f.read_bytes());return
  if not self.auth():return self.json_(403,{'error':'Connect using the pairing code shown by your local runner'})
  if path=='/health':return self.json_(200,{'name':'GBP Audit by Amrendar','version':'1.0','ready':True})
  parts=path.strip('/').split('/')
  if len(parts)>=2 and parts[0]=='jobs' and parts[1] in JOBS:
   job=JOBS[parts[1]]
   if len(parts)==2:return self.json_(200,job)
   if len(parts)==4 and parts[2]=='file':
    name=urllib.parse.unquote(parts[3]);folder=(ROOT/parts[1]).resolve();f=(folder/name).resolve()
    if folder not in f.parents or not f.is_file() or name not in job.get('files',[]):return self.json_(404,{'error':'Unknown output'})
    self.headers_(200,'application/octet-stream');self.end_headers();self.wfile.write(f.read_bytes());return
  return self.json_(404,{'error':'Not found'})
 def do_POST(self):
  if not self.auth():return self.json_(403,{'error':'Origin or pairing code rejected'})
  if self.path!='/jobs':return self.json_(404,{'error':'Not found'})
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=5000000:raise ValueError('Upload must be smaller than 5 MB')
   body=json.loads(self.rfile.read(size))
   if body.get('consent') is not True:raise ValueError('Approve public read-only auditing first')
   with LOCK:
    if any(j['status'] in ['queued','running'] for j in JOBS.values()):raise ValueError('An audit is already running. Wait for it to finish.')
   if body.get('file'):
    raw=base64.b64decode(body['file'],validate=True);ext=body.get('extension')
    if ext not in ['csv','xlsx']:raise ValueError('Use CSV or XLSX')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
     p=pathlib.Path(tmp)/('upload.'+ext);p.write_bytes(raw)
     if ext=='xlsx':
      with zipfile.ZipFile(p) as z:
       if sum(x.file_size for x in z.infolist())>30000000:raise ValueError('Expanded workbook is too large')
     rows=audit.load_rows(p)
   else:rows=body.get('rows')
   rows=validate_rows(rows);media=int(body.get('media_limit',10))
   if not 0<=media<=50:raise ValueError('Media sample must be 0–50')
   brand=body.get('brand') or {};brand={k:str(brand.get(k,''))[:100] for k in ['client','color']}
   if brand['color'] and not audit.re.fullmatch('#[0-9a-fA-F]{6}',brand['color']):raise ValueError('Use a hex brand colour')
   jid=secrets.token_hex(12);JOBS[jid]={'id':jid,'status':'queued','messages':[],'files':[]};POOL.submit(work,jid,rows,media,brand)
   self.json_(202,{'id':jid})
  except (ValueError,TypeError,KeyError,StopIteration,zipfile.BadZipFile) as e:self.json_(400,{'error':str(e) or 'Invalid upload'})

def main():
 global PORT
 parser=argparse.ArgumentParser(description=__doc__);args=parser.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 print(f'GBP Audit by Amrendar\nOpen http://127.0.0.1:{PORT}\nPairing code: {TOKEN}\nKeep this window open. Ctrl+C stops the runner. No extension or Google password required.',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.shutdown()
if __name__=='__main__':main()
