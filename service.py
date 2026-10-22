"""Single-process hosted worker. Serve with: uvicorn service:app --host 0.0.0.0."""
import concurrent.futures,contextlib,hashlib,json,logging,os,pathlib,re,secrets,shutil,threading,time,zipfile
from collections import defaultdict,deque
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse,Response
import audit
from job_support import prepare_payload,files_for,package_outputs,rebuild_reports

ROOT=pathlib.Path(os.environ.get('AUDIT_DATA_DIR','service-data')).resolve()
ORIGINS={x.strip().rstrip('/') for x in os.environ.get('AUDIT_ALLOWED_ORIGINS','https://askamrendar.github.io').split(',') if x.strip()}
TTL=int(os.environ.get('AUDIT_RETENTION_HOURS','24'))*3600
MAX_ROWS=int(os.environ.get('AUDIT_MAX_STORES','10'))
EPHEMERAL=os.environ.get('AUDIT_STORAGE_EPHEMERAL','false').lower()=='true'
JOBS={};LOCK=threading.RLock();POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
ATTEMPTS=defaultdict(deque);LOG=logging.getLogger('gbp.audit')

def persist(job):
 folder=ROOT/job['id'];folder.mkdir(parents=True,exist_ok=True)
 tmp=folder/'job-state.tmp';tmp.write_text(json.dumps(job));tmp.replace(folder/'job-state.json')

def cleanup():
 with LOCK:
  cutoff=time.time()-TTL
  for jid,job in list(JOBS.items()):
   if job['created_at']<cutoff and job['status'] not in ['queued','running']:
    shutil.rmtree(ROOT/jid,ignore_errors=True);JOBS.pop(jid,None)

def load_jobs():
 ROOT.mkdir(parents=True,exist_ok=True)
 for file in ROOT.glob('*/job-state.json'):
  try:
   job=json.loads(file.read_text())
   if not re.fullmatch('[a-f0-9]{24}',job['id']) or file.parent.name!=job['id']:continue
   if job['status'] in ['queued','running']:
    job['status']='failed';job['messages'].append('Service restarted. Rebuild reports from saved data, or start a new audit if collection was incomplete.')
   job['files']=files_for(file.parent);JOBS[job['id']]=job
  except (OSError,ValueError,KeyError):LOG.warning('Could not restore a job record')
 cleanup()

@contextlib.asynccontextmanager
async def lifespan(app):
 load_jobs();yield

app=FastAPI(title='GBP Audit by Amrendar',docs_url=None,redoc_url=None,lifespan=lifespan)

@app.middleware('http')
async def boundary(request,call_next):
 origin=request.headers.get('origin');own=str(request.base_url).rstrip('/')
 if origin and origin not in ORIGINS|{own}:return JSONResponse({'error':'Origin rejected'},403)
 if request.method=='OPTIONS':response=Response(status_code=204)
 else:response=await call_next(request)
 if origin:
  response.headers['Access-Control-Allow-Origin']=origin
  response.headers['Vary']='Origin'
  response.headers['Access-Control-Allow-Headers']='Authorization, Content-Type'
  response.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
 response.headers['Cache-Control']='no-store'
 response.headers['X-Content-Type-Options']='nosniff'
 return response

@app.exception_handler(HTTPException)
async def api_error(request,exc):return JSONResponse({'error':exc.detail},exc.status_code)

def owner(request):
 token=request.headers.get('authorization','').removeprefix('Bearer ')
 if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise HTTPException(401,'Your session expired. Reopen the app to connect again.')
 return hashlib.sha256(token.encode()).hexdigest()

def owned(request,jid):
 cleanup();job=JOBS.get(jid)
 if not job or not secrets.compare_digest(job['owner'],owner(request)):raise HTTPException(404,'Audit not found or expired')
 return job

def public(job):return {k:v for k,v in job.items() if k!='owner'}

def limit(request):
 address=request.client.host if request.client else 'unknown';now=time.time()
 with LOCK:
  # Deliberately use the socket address, never an untrusted forwarded header.
  for key in list(ATTEMPTS):
   while ATTEMPTS[key] and ATTEMPTS[key][0]<now-3600:ATTEMPTS[key].popleft()
   if not ATTEMPTS[key]:ATTEMPTS.pop(key,None)
  bucket=ATTEMPTS[address]
  if len(bucket)>=30:raise HTTPException(429,'Too many requests. Try again later.')
  bucket.append(now)

async def payload(request):
 length=request.headers.get('content-length')
 if length and (not length.isdigit() or int(length)>5000000):raise HTTPException(413,'Upload must be below 5 MB')
 raw=bytearray()
 async for chunk in request.stream():
  raw.extend(chunk)
  if len(raw)>5000000:raise HTTPException(413,'Upload must be below 5 MB')
 try:return json.loads(raw)
 except (ValueError,UnicodeError):raise HTTPException(400,'Invalid JSON request')

@app.get('/api/health')
def health():return {'name':'GBP Audit by Amrendar','version':'1.3','ready':True,'mode':'hosted','retention_hours':TTL//3600,'max_stores':MAX_ROWS,'ephemeral_storage':EPHEMERAL}

@app.post('/api/session')
def session(request:Request):
 limit(request);return {'token':secrets.token_urlsafe(32)}

@app.get('/api/jobs')
def history(request:Request):
 who=owner(request);cleanup()
 with LOCK:records=[public(x) for x in JOBS.values() if x['owner']==who]
 return {'jobs':sorted(records,key=lambda x:x['created_at'],reverse=True)[:20]}

def work(jid,rows,media,brand,rebuild=False):
 job=JOBS[jid];folder=ROOT/jid;browser=ROOT/'.browsers'/jid
 try:
  job['status']='running';persist(job)
  def log(message):
   with LOCK:job['messages'].append(str(message).replace(str(ROOT),'audit data'));persist(job)
  if rebuild:job['files']=rebuild_reports(folder)
  else:
   audit.run(rows,folder,browser,headless=True,channel='chromium',media_limit=media,brand=brand,log=log)
   job['files']=package_outputs(folder)
  job['status']='completed'
 except Exception:
  LOG.exception('Audit/export job %s failed',jid)
  job['status']='failed';job['files']=files_for(folder)
  job['messages'].append('Collection or export stopped. Saved files remain available. Try Rebuild PowerPoint if audit data was saved; otherwise review the last collection step.')
 finally:
  shutil.rmtree(browser,ignore_errors=True);persist(job)

@app.post('/api/jobs',status_code=202)
async def create(request:Request):
 who=owner(request);limit(request);body=await payload(request);cleanup();jid=secrets.token_hex(12)
 with LOCK:
  active=[j for j in JOBS.values() if j['status'] in ['queued','running']]
  if any(j['owner']==who for j in active):raise HTTPException(409,'Your audit is already running. Open it in Recent audits.')
  if len(active)>=4:raise HTTPException(429,'The audit queue is full. Try again after a job finishes.')
  try:
   rows,media,brand=prepare_payload(body,ROOT/jid)
   if len(rows)>MAX_ROWS:raise ValueError(f'Hosted jobs allow up to {MAX_ROWS} stores at once')
   if media>20:raise ValueError('Hosted media sample must be 0, 10 or 20 items per profile')
  except (ValueError,TypeError,KeyError,OSError,EOFError,zipfile.BadZipFile) as exc:
   shutil.rmtree(ROOT/jid,ignore_errors=True);raise HTTPException(400,str(exc))
  JOBS[jid]={'id':jid,'owner':who,'created_at':time.time(),'status':'queued','messages':['Audit queued. Collection and reports run in the background.'],'files':[]}
  persist(JOBS[jid]);POOL.submit(work,jid,rows,media,brand)
 return {'id':jid}

@app.get('/api/jobs/{jid}')
def status(request:Request,jid:str):return public(owned(request,jid))

@app.post('/api/jobs/{jid}/export')
def export(request:Request,jid:str):
 job=owned(request,jid);limit(request)
 with LOCK:
  if any(j['status'] in ['queued','running'] for j in JOBS.values()):raise HTTPException(409,'Wait for the active queue to finish before rebuilding a report')
  if not list((ROOT/jid).glob('*/audit.json')):raise HTTPException(400,'No saved audit data is available to rebuild')
  job['status']='queued';job['messages'].append('Rebuilding reports from saved data; Google is not queried again.');persist(job);POOL.submit(work,jid,[],0,{},True)
 return public(job)

@app.get('/api/jobs/{jid}/file/{name:path}')
def download(request:Request,jid:str,name:str):
 job=owned(request,jid);folder=(ROOT/jid).resolve();file=(folder/name).resolve()
 if name not in job.get('files',[]) or folder not in file.parents or not file.is_file():raise HTTPException(404,'File not found or expired. Open the audit and rebuild the report if saved data is available.')
 return FileResponse(file,filename=file.name)

@app.get('/config.js')
def config():return Response('window.GBP_AUDIT_CONFIG = '+json.dumps({'apiBase':'/api','hosted':True,'maxStores':MAX_ROWS,'ephemeral':EPHEMERAL})+';',media_type='application/javascript')

@app.get('/')
def index():return FileResponse(pathlib.Path(__file__).parent/'docs/index.html')

@app.get('/{asset}')
def static(asset:str):
 if asset not in ['app.js','style.css','template.csv']:raise HTTPException(404,'Not found')
 return FileResponse(pathlib.Path(__file__).parent/'docs'/asset)
