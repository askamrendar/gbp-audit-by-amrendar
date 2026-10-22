"""Shared upload validation and recoverable report packaging."""
import base64,io,json,pathlib,re,tempfile,zipfile
from PIL import Image
import audit

def validate_rows(rows):
 if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('Supply 1–100 stores per run')
 for row in rows:
  if not isinstance(row,dict):raise ValueError('Each store must be a record')
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(row.get('store_code',''))):raise ValueError('Store code: use letters, numbers, hyphens or underscores')
  audit.maps_url(str(row.get('maps_url','')))
  if not 1<=len(str(row.get('keyword','')).strip())<=200:raise ValueError('A keyword is required (up to 200 characters)')
  values=[str(row.get(k) if row.get(k) is not None else '').strip() for k in ['search_latitude','search_longitude']]
  if bool(values[0])!=bool(values[1]):raise ValueError('Supply both search coordinates together')
  for key,lo,hi in [('search_latitude',-90,90),('search_longitude',-180,180)]:
   if row.get(key) not in [None,''] and not lo<=float(row[key])<=hi:raise ValueError('Invalid search coordinates')
 return rows

def prepare_payload(body,folder):
 if not isinstance(body,dict):raise ValueError('Supply an audit request')
 if body.get('consent') is not True:raise ValueError('Approve public read-only auditing first')
 if body.get('file'):
  raw=base64.b64decode(body['file'],validate=True);ext=body.get('extension')
  if len(raw)>3500000:raise ValueError('Store file must be below 3.5 MB')
  if ext not in ['csv','xlsx']:raise ValueError('Use CSV or XLSX')
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/('upload.'+ext);p.write_bytes(raw)
   if ext=='xlsx':
    with zipfile.ZipFile(p) as z:
     if sum(x.file_size for x in z.infolist())>30000000:raise ValueError('Expanded workbook is too large')
   rows=audit.load_rows(p)
 else:rows=body.get('rows')
 rows=validate_rows(rows);media=int(body.get('media_limit',10))
 if not 0<=media<=50:raise ValueError('Media sample must be 0–50')
 brand=body.get('brand') or {}
 if not isinstance(brand,dict):raise ValueError('Invalid branding')
 brand={k:str(brand.get(k,''))[:100] for k in ['client','color','accent','agency']}
 for key in ['color','accent']:
  if brand[key] and not re.fullmatch('#[0-9a-fA-F]{6}',brand[key]):raise ValueError('Use a hex '+key+' colour')
 if body.get('logo'):
  raw=base64.b64decode(body['logo'],validate=True)
  if len(raw)>1000000:raise ValueError('Logo must be below 1 MB')
  try:
   with Image.open(io.BytesIO(raw)) as im:
    if im.format not in ['PNG','JPEG'] or im.width*im.height>16000000:raise ValueError('Use a PNG or JPEG logo below 16 megapixels')
    im.verify()
   target=pathlib.Path(folder)/'branding/agency-logo.png';target.parent.mkdir(parents=True,exist_ok=True)
   with Image.open(io.BytesIO(raw)) as im:im.convert('RGBA').save(target,'PNG')
   brand['logo_path']=str(target)
  except (OSError,Image.DecompressionBombError) as exc:raise ValueError('Invalid or oversized logo image') from exc
 return rows,media,brand

def files_for(folder):
 folder=pathlib.Path(folder)
 return sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p.suffix in ['.pptx','.zip','.csv','.json'] and p.name!='job-state.json')

def package_outputs(folder):
 folder=pathlib.Path(folder);folder.mkdir(parents=True,exist_ok=True)
 # A half-written file must never be advertised as a successful PowerPoint.
 for p in folder.rglob('*.pptx'):
  with zipfile.ZipFile(p) as z:
   if z.testzip() or '[Content_Types].xml' not in z.namelist():raise ValueError('PowerPoint validation failed; rebuild the report from saved data')
 archive=folder/'audit-results.zip';temporary=folder/'audit-results.zip.tmp'
 with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
  for p in folder.rglob('*'):
   if p.is_file() and p not in [archive,temporary] and p.name!='job-state.json':z.write(p,p.relative_to(folder).as_posix())
 temporary.replace(archive)
 return files_for(folder)

def rebuild_reports(folder):
 from report import export_ppt,export_portfolio
 import hashlib
 groups={};folder=pathlib.Path(folder)
 for source in sorted(folder.glob('*/audit.json')):
  data=json.loads(source.read_text());export_ppt(data,source.parent/'audit-draft.pptx')
  key=(data['input']['keyword'],data.get('ranking',{}).get('method','exploratory_maps_area_view'));groups.setdefault(key,[]).append(data)
 if not groups:raise ValueError('No saved audit data is available for report rebuilding')
 for (keyword,method),group in groups.items():
  if len(group)>1:export_portfolio(group,folder/('all-stores-'+hashlib.sha256((keyword+method).encode()).hexdigest()[:8]+'.pptx'))
 return package_outputs(folder)
