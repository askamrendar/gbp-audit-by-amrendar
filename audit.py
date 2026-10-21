#!/usr/bin/env python3
"""Local, extension-free, read-only GBP audit runner. See README for coverage limits."""
import argparse,csv,datetime as dt,hashlib,html,ipaddress,json,pathlib,re,socket,sys,time
from urllib.parse import urlparse,quote,unquote
BASE=pathlib.Path(__file__).resolve().parent

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def dump(path,obj):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False))
def maps_url(url):
 p=urlparse(url);h=(p.hostname or '').lower()
 if p.scheme!='https' or not (h in ['maps.app.goo.gl','maps.google.com','goo.gl'] or re.fullmatch(r'(www\.)?google\.(com|co\.[a-z]{2}|[a-z]{2})',h)) or p.username or p.password:raise ValueError('Use an HTTPS Google Maps business profile link')
 if h=='goo.gl' and not p.path.startswith('/maps/'):raise ValueError('Use a Maps short link')
 if h not in ['maps.app.goo.gl','maps.google.com','goo.gl'] and not p.path.startswith('/maps'):raise ValueError('Use a Google Maps profile, not a generic Google page')
 return url

def public_url(url):
 p=urlparse(url)
 if p.scheme not in ['https','http'] or not p.hostname or p.username or p.password:return False
 try:
  return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80)))
 except (socket.gaierror,ValueError):return False

def identity(url):
 s=unquote(url);m=re.search(r'[?&]cid=(\d+)',s)
 if m:return 'cid-'+m[1]
 m=re.search(r'0x[0-9a-f]+:(0x[0-9a-f]+)',s,re.I)
 if m:return 'cid-'+str(int(m[1],16))
 m=re.search(r'(?:query_place_id|place_id)=([^&]+)',s)
 return 'place-'+m[1] if m else None

def load_rows(path):
 p=pathlib.Path(path)
 if p.suffix.lower()=='.xlsx':
  from openpyxl import load_workbook
  w=load_workbook(p,read_only=True,data_only=True);it=iter(w.active.values);headers=[str(c or '').strip() for c in next(it)];rows=[dict(zip(headers,r)) for r in it if any(c is not None for c in r)];w.close()
 elif p.suffix.lower()=='.csv':
  with p.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 else:raise ValueError('Upload CSV or XLSX')
 for n,r in enumerate(rows,2):
  for k in ['store_code','maps_url','keyword']:
   if not str(r.get(k) or '').strip():raise ValueError(f'Row {n}: missing {k}')
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(r['store_code'])):raise ValueError(f'Row {n}: unsafe store code')
  maps_url(r['maps_url'])
 return rows

def blocked(page):
 u=page.url.lower();s=page.locator('body').inner_text(timeout=8000)
 if '/sorry/' in u or page.locator('iframe[src*="recaptcha"]').count() or re.search(r'unusual traffic|not a robot|automated queries',s,re.I):return 'Google access/CAPTCHA block: manual action required; not bypassed'
 if 'accounts.google.com' in u:return 'Sign-in page reached; no credentials entered'
 return None

def settle(page):
 page.locator('body').wait_for(timeout=20000)
 try:page.locator('h1, [role="feed"], [role="main"]').first.wait_for(timeout=15000)
 except Exception:pass

def capture(page,folder,stem):
 folder.mkdir(parents=True,exist_ok=True);shot=folder/(stem+'.png');text=folder/(stem+'.txt')
 page.screenshot(path=str(shot),full_page=False);body=page.locator('body').inner_text(timeout=10000);text.write_text(body)
 return {'url':page.url,'observed_at':now(),'screenshot':str(shot),'text_artifact':str(text),'body':body}

def website(page,url,folder,stem):
 if not public_url(url):return {'requested_url':url,'error':'Non-public or invalid website destination not opened'}
 try:
  response=page.goto(url,wait_until='domcontentloaded',timeout=30000);page.locator('body').wait_for(timeout=10000)
  data=page.evaluate('''() => ({title:document.title,canonical:document.querySelector('link[rel="canonical"]')?.href,robots:document.querySelector('meta[name="robots"]')?.content,description:document.querySelector('meta[name="description"]')?.content,headings:Array.from(document.querySelectorAll('h1,h2,h3')).map(e=>({tag:e.tagName,text:e.innerText})),jsonld:Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(e=>e.textContent),iframes:Array.from(document.querySelectorAll('iframe')).map(e=>({src:e.src,title:e.title})),links:Array.from(document.querySelectorAll('a[href]')).map(e=>({text:e.innerText,href:e.href})),body:document.body.innerText})''')
  data.update(capture(page,folder,stem),requested_url=url,status_code=response.status if response else None)
  data['schema']=[]
  for raw in data['jsonld']:
   try:data['schema'].append({'syntax':'parsed','value':json.loads(raw)})
   except ValueError:data['schema'].append({'syntax':'invalid'})
  data['page_type']='locator' if re.search(r'store.?locator|our.?stores',page.url,re.I) else 'homepage' if urlparse(page.url).path in ['/',''] else 'other page; branch identity needs review'
  data['embed_assessment']='Iframe inventory collected; review/social embed identity and actual rendered content require review. Social links alone are not embeds.'
  return data
 except Exception as exc:return {'requested_url':url,'error':type(exc).__name__+': destination unavailable during test'}

def gallery(page,folder,limit):
 result={'items':[],'coverage':'sample','blocker':None}
 try:
  entry=page.get_by_role('button',name=re.compile(r'^\d[\d,]* Photos$'))
  if not entry.count():entry=page.get_by_role('button',name='See photos',exact=True)
  if not entry.count():result['blocker']='No gallery entry exposed in this interface';return result
  entry.first.click();page.wait_for_function('/(Photo|Video) *-/.test(document.body.innerText)',timeout=10000)
  seen=set()
  for n in range(limit):
   # Wait on a changed, stable URL rather than storing the preceding item's identity.
   page.wait_for_function('location.href.includes("!1s")',timeout=10000)
   previous=None
   for _ in range(12):
    current=page.url;body=page.locator('body').inner_text();label=re.search(r'(Photo|Video)\s*-\s*([^\n]+)',body)
    signature=(current,label.group(0) if label else '')
    if signature==previous and label:break
    previous=signature;page.wait_for_timeout(200)
   media_id=(re.findall(r'!1s([^!]+)',unquote(page.url)) or [page.url])[0]
   if media_id in seen:result['blocker']='Selected item did not advance; stopped to avoid duplicate evidence';break
   seen.add(media_id);cap=capture(page,folder,'media-'+str(n+1).zfill(2));cap.update(media_id=media_id,format=label[1].lower() if label else 'unknown',date_label=label[2] if label else None,published_at=None,uploader_role='unknown',image_type=None,classification_method=None,classification_evidence=None,evidence=cap['screenshot'],visual_review_required=True)
   result['items'].append(cap)
   nxt=page.get_by_role('button',name='Next',exact=True)
   if not nxt.count() or not nxt.is_enabled():result['blocker']='End of exposed gallery reached; full history not independently established';break
   if n+1<limit:
    old=page.url;nxt.click()
    try:page.wait_for_function('(old)=>location.href!==old',arg=old,timeout=8000)
    except Exception:result['blocker']='Gallery did not expose another item';break
  if not result['blocker']:result['blocker']='Configured sample limit reached'
 except Exception as exc:result['blocker']='Gallery collection unavailable: '+type(exc).__name__
 return result

def profile(context,url,folder,media_limit,expected_id=None):
 page=context.new_page();result={'requested_url':url,'attempted_at':now(),'errors':[]}
 try:
  page.goto(url,wait_until='domcontentloaded',timeout=30000);settle(page)
  if blocked(page):result.update(blocker=blocked(page),evidence=capture(page,folder,'blocked'));return result
  result.update(capture(page,folder,'profile'));result['entity_id']=identity(page.url) or identity(url)
  h=page.locator('h1');result['name']=h.first.inner_text() if h.count() else None
  if not result['name']:result['errors'].append('No business heading; identity unresolved');return result
  if expected_id and result['entity_id'] and expected_id!=result['entity_id']:result['errors'].append('Exact profile identity mismatch');return result
  for field,pattern in [('address',r'^Address:'),('phone',r'^Phone:')]:
   loc=page.get_by_role('button',name=re.compile(pattern));result[field]=loc.first.get_attribute('aria-label') if loc.count() else None
  category=page.locator('button[jsaction*="category"]')
  result['category']=category.first.inner_text() if category.count() else None
  reviews=page.get_by_role('button',name=re.compile(r'[\d,]+ reviews'))
  result['review_count_label']=reviews.first.get_attribute('aria-label') if reviews.count() else None
  website_link=page.locator('a[data-item-id="authority"]')
  if not website_link.count():website_link=page.get_by_role('link',name=re.compile(r'^Website:'))
  result['website']=website_link.first.get_attribute('href') if website_link.count() else None
  result['website_link_state']='present' if result['website'] else 'missing' if page.get_by_role('button',name='Add website',exact=True).count() else 'not_exposed'
  hours=page.get_by_role('button',name=re.compile('Show open hours for the week'))
  if hours.count():
   try:hours.first.click();result['hours_evidence']=capture(page,folder,'hours');page.keyboard.press('Escape')
   except Exception:result['errors'].append('Full hours could not be expanded')
  about=page.get_by_role('tab',name=re.compile('About'))
  if about.count():
   try:about.first.click();result['about_evidence']=capture(page,folder,'about');page.get_by_role('tab',name=re.compile('Overview')).first.click()
   except Exception:result['errors'].append('About view unavailable')
  review_tab=page.get_by_role('tab',name='Reviews',exact=True)
  if review_tab.count():
   try:
    review_tab.first.click();page.locator('[data-review-id]').first.wait_for(timeout=8000)
    result['reviews_evidence']=capture(page,folder,'reviews')
    result['review_sample']=page.locator('[data-review-id]').evaluate_all('(els)=>els.slice(0,10).map(e=>({id:e.getAttribute("data-review-id"),text:e.innerText}))')
    result['reviews_summary']=str(len(result['review_sample']))+' visible reviews captured; default order, not a matched-period reply rate'
    page.get_by_role('tab',name='Overview',exact=True).first.click()
   except Exception:result['errors'].append('Review sample unavailable')
  posts=page.get_by_role('button',name='See local posts',exact=True)
  if posts.count():
   try:posts.click();result['post_evidence']=capture(page,folder,'post');page.goto(result['url'],wait_until='domcontentloaded');settle(page)
   except Exception:result['errors'].append('Post detail unavailable')
  if media_limit:result['gallery']=gallery(page,folder,media_limit)
  result['resolved_url']=page.url
  if result['website']:
   wp=context.new_page()
   try:
    result['website_audit']=website(wp,result['website'],folder,'website')
    links=result['website_audit'].get('links',[])
    candidates=[x for x in links if re.search(r'contact|store|location',x['text'],re.I) and urlparse(x['href']).hostname==urlparse(wp.url).hostname]
    result['supplementary_pages']=[]
    for n,link in enumerate(candidates[:2]):
     if link['href']!=wp.url:result['supplementary_pages'].append(website(wp,link['href'],folder,'supplement-'+str(n+1)))
   finally:wp.close()
 except Exception as exc:result['errors'].append(type(exc).__name__+': profile collection interrupted')
 finally:page.close()
 return result

def rank_search(context,keyword,center,folder):
 page=context.new_page();r={'keyword':keyword,'method':'exploratory_maps_area_view','physical_origin_verified':False,'requested_center':center,'observed_at':now(),'results':[],'valid':False}
 try:
  url='https://www.google.com/maps/search/'+quote(keyword,safe='')+'/'
  if center:url+='@'+center+',15z'
  page.goto(url,wait_until='domcontentloaded',timeout=30000);settle(page)
  if blocked(page):r['blocker']=blocked(page);return r
  try:page.locator('a[href*="/maps/place/"]').first.wait_for(timeout=15000)
  except Exception:r['blocker']='No result-list business links exposed';r.update(capture(page,folder,'search'));return r
  r.update(capture(page,folder,'search'))
  entries=page.locator('a[href*="/maps/place/"]').evaluate_all('(els)=>els.map(e=>({url:e.href,name:e.getAttribute("aria-label")||e.innerText,card:e.closest("[role=article]")?.innerText||e.parentElement?.innerText||""}))')
  seen=set()
  for x in entries:
   eid=identity(x['url'])
   if not eid or eid in seen or not x['name'].strip():continue
   # Discard an explicitly labelled sponsored card, retaining evidence for review.
   if re.search(r'\bSponsored\b|\bAd\s*·',x['card']):continue
   seen.add(eid);r['results'].append(dict(x,entity_id=eid,position=len(r['results'])+1))
  r['valid']=len(r['results'])>=3
  r['sponsored_exclusion']='Explicit sponsored labels excluded; verify result screenshot before accepting top-three order.'
  if not r['valid']:r['blocker']='Fewer than three matched unsponsored candidates; no top-three cohort asserted'
 except Exception as exc:r['blocker']=type(exc).__name__+': rank collection interrupted'
 finally:page.close()
 return r

def assess(p):
 checks=[dict(x,status='Unknown',finding='Evidence not collected for this check in this version.',next_input=x['evidence_required']) for x in json.loads((BASE/'checklist.json').read_text())]
 def set_(id,status,finding,next_input=''):
  x=next(x for x in checks if x['id']==id);x.update(status=status,finding=finding,next_input=next_input)
 if p.get('name'):
  set_('A03','Partial','Displayed name: '+p['name'],'Compare verified storefront branding')
 if p.get('address'):set_('A05','Partial',p['address'],'Confirm branch/unit and postal details')
 if p.get('phone'):set_('B05','Partial',p['phone'],'Confirm actual branch routing; no call placed')
 if p.get('hours_evidence'):set_('B03','Partial','Expanded hours captured','Compare store-confirmed schedule and special hours')
 if p.get('about_evidence'):set_('B10','Partial','Public About attributes captured','Review factual accuracy; absence not inferred')
 state=p.get('website_link_state')
 if state=='missing':set_('B06','Fail','Public profile offers Add website; no linked website found','Approve correct branch URL')
 if p.get('website_audit'):
  w=p['website_audit'];set_('B06','Partial','Linked destination: '+w.get('url',w.get('requested_url','')),'Verify branch identity and journey')
  if not w.get('error'):
   set_('E08','Partial','Title/headings captured: '+w.get('title',''),'Review locality, intent and factual usefulness')
   set_('E05','Partial','Canonical: '+str(w.get('canonical')),'Verify intended branch canonical and redirect chain')
   set_('E13','Partial','Structured-data blocks: '+str(len(w.get('schema',[]))),'Review branch entities and visible facts')
   set_('E14','Partial','JSON-LD syntax parsing completed','Vocabulary, visible-fact and Google eligibility checks remain separate')
 if p.get('gallery',{}).get('items'):set_('B11','Partial',str(len(p['gallery']['items']))+' media items captured; visual classification pending','Review saved media screenshots; exact owner upload history unverified')
 if p.get('category'):set_('B01','Partial','Displayed category: '+p['category'],'Confirm primary category relevance and complete additional categories')
 if p.get('review_sample'):set_('C01','Partial',p.get('reviews_summary','Visible review sample captured'),'Inspect actual replies and dates; use a matched period and denominator')
 if p.get('post_evidence'):set_('B12','Partial','Visible post captured','Review image/text, date, offer validity and real CTA')
 if p.get('blocker'):
  for c in checks:c['finding']='Collection blocked: '+p['blocker']
 return checks

from report import export_ppt

def run(rows,out,profile_dir,headless=False,executable=None,media_limit=10,channel='chrome',log=print,brand=None):
 from playwright.sync_api import sync_playwright
 out=pathlib.Path(out).resolve();out.mkdir(parents=True,exist_ok=True);profile_dir=pathlib.Path(profile_dir).resolve()
 normal=pathlib.Path.home()/'Library/Application Support/Google/Chrome'
 if profile_dir==normal or normal in profile_dir.parents:raise ValueError('Use the separate audit browser directory, not your regular Chrome profile')
 with sync_playwright() as pw:
  args=dict(user_data_dir=str(profile_dir),headless=headless,viewport={'width':1280,'height':900},locale='en-GB')
  if executable:args['executable_path']=executable
  else:args['channel']=channel
  context=pw.chromium.launch_persistent_context(**args)
  # No access to private/local network destinations; no profile mutation UI is invoked.
  def route(req):
   u=urlparse(req.request.url)
   if u.scheme in ['http','https'] and not public_url(req.request.url):req.abort()
   else:req.continue_()
  context.route('**/*',route)
  try:
   for row in rows:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(row.get('store_code',''))):raise ValueError('Invalid store code')
    if not str(row.get('keyword','')).strip():raise ValueError('Keyword is required')
    folder=out/(str(row['store_code'])+'-'+hashlib.sha256(row['keyword'].encode()).hexdigest()[:8]+'-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));folder.mkdir(exist_ok=True);data={'input':row,'started_at':now(),'profiles':[],'brand':brand or {}}
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(row['store_code'])):raise ValueError('Store code must contain only letters, numbers, hyphens and underscores')
    log('Collecting target '+str(row['store_code']));target=profile(context,maps_url(row['maps_url']),folder/'target',media_limit,identity(row['maps_url']));data['profiles'].append(target)
    if not target.get('name') or not target.get('entity_id') or target.get('blocker') or 'Exact profile identity mismatch' in target.get('errors',[]):
     data['identity_review_required']=True
    if row.get('business_name') and target.get('name') and row['business_name'].strip().casefold()!=target['name'].strip().casefold():data['identity_review_required']=True;data['identity_warning']='Expected/displayed business names differ; confirm branch before using comparison.'
    center=None
    if row.get('search_latitude') is not None and row.get('search_longitude') is not None and str(row.get('search_latitude','')).strip() and str(row.get('search_longitude','')).strip():
     lat,lon=float(row['search_latitude']),float(row['search_longitude'])
     if not(-90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid search coordinates')
     center=f'{lat},{lon}'
    if not center:
     m=re.search(r'!3d(-?[\d.]+)!4d(-?[\d.]+)',unquote(target.get('resolved_url',target.get('url',''))))
     if m:center=m[1]+','+m[2]
    if not data.get('identity_review_required'):
     log('Collecting keyword results');data['ranking']=rank_search(context,row['keyword'],center,folder/'ranking') if center else {'valid':False,'results':[],'blocker':'Search location unresolved. Supply search_latitude and search_longitude; no top-three cohort asserted.'}
     if data['ranking']['valid']:
      seen={target.get('entity_id')}
      for n,c in enumerate(data['ranking']['results'][:3],1):
       if c['entity_id'] in seen:continue
       seen.add(c['entity_id']);log('Collecting competitor '+str(n));data['profiles'].append(profile(context,c['url'],folder/('competitor-'+str(n)),media_limit,c['entity_id']))
    else:data['ranking']={'valid':False,'blocker':'Target identity or collection unresolved; competitor loop not started'}
    for p in data['profiles']:p['checks']=assess(p)
    data['completed_at']=now();dump(folder/'audit.json',data)
    with (folder/'checklist.csv').open('w',newline='') as f:
     w=csv.writer(f);w.writerow(['entity','check_id','check','status','finding','next_input'])
     for p in data['profiles']:
      for c in p['checks']:w.writerow([p.get('name'),c['id'],c['check'],c['status'],c['finding'],c['next_input']])
    export_ppt(data,folder/'audit-draft.pptx');log('Saved '+str(folder))
  finally:context.close()
 return str(out)

def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--maps-url');a.add_argument('--keyword');a.add_argument('--store-code',default='STORE1');a.add_argument('--input');a.add_argument('--search-latitude',type=float);a.add_argument('--search-longitude',type=float);a.add_argument('--out',default='runs');a.add_argument('--browser-profile',default=str(BASE/'.audit-browser'));a.add_argument('--headless',action='store_true');a.add_argument('--executable');a.add_argument('--media-limit',type=int,default=10);a.add_argument('--yes',action='store_true');ns=a.parse_args()
 if not 0<=ns.media_limit<=50:a.error('media-limit must be 0..50')
 rows=load_rows(ns.input) if ns.input else [{'store_code':ns.store_code,'maps_url':ns.maps_url,'keyword':ns.keyword,'search_latitude':ns.search_latitude,'search_longitude':ns.search_longitude}]
 if not all(r.get('maps_url') and r.get('keyword') for r in rows):a.error('Supply --maps-url and --keyword, or --input file')
 consent=pathlib.Path(ns.browser_profile)/'audit-consent.json'
 if not consent.exists():
  print('This opens Google Maps and linked public websites, captures audit evidence locally, and creates reports. It does not edit profiles or bypass access blocks.')
  if not ns.yes and input('Approve read-only browser auditing on this computer? [y/N] ').lower()!='y':return
  dump(consent,{'approved_at':now(),'scope':'read-only local browser audits; no account edits, CAPTCHA solving or paid APIs'})
 run(rows,ns.out,ns.browser_profile,ns.headless,ns.executable,ns.media_limit)
if __name__=='__main__':main()
