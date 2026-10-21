#!/usr/bin/env python3
"""Read-only GBP media collection and evidence summarization; Python standard library.
Public browser collectors/reviewers write the normalized inventory schema in
references/media-audit.md. No image download, classification model or browser login.
"""
import argparse, collections, csv, datetime as dt, json, os, pathlib, re, sys
import urllib.request, urllib.parse, urllib.error
UTC=dt.timezone.utc

def stamp(value):
    value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None: raise ValueError('Timestamp must include timezone')
    return value.astimezone(UTC)

def save(path, data):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')

def blank(entity, observed_at=None):
    return {'schema_version':1,'entity_id':entity['entity_id'],'name':entity.get('name',''),
      'profile_url':entity.get('actual_url',entity.get('profile_url',entity.get('url',''))),
      'observed_at':observed_at or dt.datetime.now(UTC).isoformat(),
      'method':'not_collected','collection_state':'not_attempted',
      'coverage':'sample','coverage_scope':'public_gallery','coverage_evidence':None,
      'media_format_coverage':[], 'attempts':[], 'reported_gallery_total':entity.get('photo_count'),
      'reported_total_observed_at':entity.get('observed_at'), 'items':[]}

def normalize_api(pages, entity, resource, observed_at, endpoint='owner'):
    if not re.fullmatch(r'accounts/[^/]+/locations/[^/]+',resource):
        raise ValueError('Use accounts/ACCOUNT/locations/LOCATION (not a Maps CID)')
    inv=blank(entity,observed_at)
    inv.update(method='gbp_api_'+endpoint,collection_state='collected',
               coverage_scope='api_'+endpoint+'_media',media_format_coverage=['photo'])
    for page in pages:
        if not isinstance(page.get('mediaItems',[]),list):raise ValueError('mediaItems must be a list')
        for item in page.get('mediaItems',[]):
            name=item.get('name','')
            if not name.startswith(resource+'/media/'):
                raise ValueError('Media item does not match specified API location')
            fmt=item.get('mediaFormat',''); category=item.get('locationAssociation',{}).get('category')
            inv['items'].append({'media_id':name,'format':{'PHOTO':'photo','VIDEO':'video'}.get(fmt,'unknown'),
              'published_at':item.get('createTime'),'date_basis':'api_create_time',
              'uploader_role':'owner' if endpoint=='owner' else 'customer',
              'image_type':None,'classification_method':None,'classification_evidence':None,
              'provider_category':category,'source_url':item.get('googleUrl') or item.get('sourceUrl'),
              'evidence':name,'attribution':item.get('attribution'),
              'notes':'Provider category is metadata, not visual verification. Video preview can be an image.'})
    inv['coverage']='complete' if pages and not pages[-1].get('nextPageToken') else 'sample'
    inv['coverage_evidence']='Saved API response pages; completeness limited to this endpoint.'
    return inv

def collect(resource, token, max_pages=20, endpoint='owner', fetch=None):
    if not re.fullmatch(r'accounts/[^/]+/locations/[^/]+',resource):raise ValueError('Invalid API location resource')
    pages=[];page_token='';seen=set();blocker=None
    for _ in range(max_pages):
        query={'pageSize':100}
        if page_token:query['pageToken']=page_token
        suffix='/customers' if endpoint=='customer' else ''
        url='https://mybusiness.googleapis.com/v4/'+resource+'/media'+suffix+'?'+urllib.parse.urlencode(query)
        try:
            if fetch:page=fetch(url)
            else:
                req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req,timeout=30) as response:page=json.load(response)
        except urllib.error.HTTPError as exc:
            blocker='API HTTP '+str(exc.code)+'; check authorized access, API availability or quota.';break
        except (urllib.error.URLError,TimeoutError):
            blocker='Network timeout or connection failure';break
        if not isinstance(page,dict) or 'error' in page:
            blocker='API returned an error or unexpected response';break
        pages.append(page);page_token=page.get('nextPageToken','')
        if not page_token:break
        if page_token in seen:blocker='Repeated pagination token';break
        seen.add(page_token)
    else:blocker='Configured page limit reached'
    return pages,blocker

def summarize(inv, as_of, days):
    end=stamp(as_of);start=end-dt.timedelta(days=days)
    stamp(inv['observed_at']);entity=inv['entity_id']
    if not entity:raise ValueError('Missing entity_id')
    unique={};duplicates=0
    for i in inv.get('items',[]):
        key=i.get('media_id') or i.get('source_url')
        if not key:raise ValueError('Each item needs a stable media_id or exact source_url')
        if not i.get('evidence'):raise ValueError('Each item needs evidence')
        if key in unique:
            if unique[key]!=i:raise ValueError('Conflicting duplicate media item: '+key)
            duplicates+=1;continue
        if i.get('format','unknown') not in ['photo','video','unknown']:raise ValueError('Invalid format')
        if i.get('uploader_role','unknown') not in ['owner','customer','unknown']:raise ValueError('Invalid uploader role')
        if i.get('published_at'):stamp(i['published_at'])
        if i.get('image_type') and not (i.get('classification_method') and i.get('classification_evidence')):
            raise ValueError('Image classification requires method and visual evidence')
        unique[key]=i
    items=list(unique.values());complete=inv.get('coverage')=='complete'
    if complete and not inv.get('coverage_evidence'):raise ValueError('Complete coverage requires evidence')
    collected=inv.get('collection_state')=='collected'
    dated=[i for i in items if i.get('published_at')]
    recent=[i for i in dated if start<=stamp(i['published_at'])<=end]
    owner=[i for i in recent if i.get('uploader_role')=='owner']
    photos=[i for i in items if i.get('format')=='photo']
    videos=[i for i in items if i.get('format')=='video']
    classified=[i for i in photos if i.get('image_type') and i.get('classification_method') in ['human_visual','agent_visual']]
    formats_known=all(i.get('format') in ['photo','video'] for i in items)
    dates_known=all(i.get('published_at') and i.get('uploader_role') in ['owner','customer'] for i in items)
    def status(has, full=False):return 'Pass' if full and collected else ('Partial' if has else 'Unknown')
    uploads_full=complete and dates_known and collected
    checks=[{'criterion_id':'form21.F18','master_ids':['B11'],'status':status(bool(owner),uploads_full),
      'finding':f'{len(owner)} confirmed owner-created items in the {days}-day window'+(' in endpoint scope.' if uploads_full else ' in inspected sample; not total upload frequency.'),
      'next_step':'Retain dated endpoint scope.' if uploads_full else 'Collect dated owner attribution and prove period coverage; do not infer cadence from gallery total.'},
      {'criterion_id':'form21.F19','master_ids':['B11','E07'],'status':status(bool(classified),bool(photos) and len(classified)==len(photos) and complete),
       'finding':f'{len(classified)}/{len(photos)} sampled photos visually classified.',
       'next_step':'Inspect entrance/exterior/interior/products and arrival usefulness; no arbitrary quota.'},
      {'criterion_id':'form21.F20','master_ids':['B11'],'status':status(bool(videos),complete and formats_known and 'video' in inv.get('media_format_coverage',[])),
       'finding':f'{len(videos)} confirmed videos'+(' in endpoint scope.' if complete and formats_known and collected and 'video' in inv.get('media_format_coverage',[]) else ' in inspected sample; no claim of total or absence.'),
       'next_step':'Inspect actual video content and dates; do not identify videos solely by image URLs.'}]
    if not items and not complete:
        for c in checks:c['finding']='No item-level evidence collected; gallery total is insufficient.'
    unknown=[{'criterion_id':c['criterion_id'],'entity_id':entity,'collection_state':inv.get('collection_state'),
      'attempts':inv.get('attempts',[]),'blocker':inv.get('blocker'),'next_input':c['next_step']} for c in checks if c['status']!='Pass']
    return {'entity_id':entity,'name':inv.get('name'),'as_of':as_of,'window_days':days,
      'window_start':start.isoformat(),'coverage':inv.get('coverage'),'coverage_scope':inv.get('coverage_scope'),
      'collection_state':inv.get('collection_state'),'deduplicated_items':len(items),'duplicates_removed':duplicates,
      'reported_gallery_total':inv.get('reported_gallery_total'),'reported_total_observed_at':inv.get('reported_total_observed_at'),
      'photo_items_observed':len(photos) if collected else None,'video_items_observed':len(videos) if collected else None,
      'confirmed_owner_items_in_window':len(owner) if collected else None,
      'visually_classified_types':dict(collections.Counter(i['image_type'] for i in classified)),
      'unknown_dates':len(items)-len(dated),'unknown_uploaders':sum(i.get('uploader_role','unknown')=='unknown' for i in items),
      'checks':checks,'collection_gaps':unknown,
      'limits':'Pass denotes documented coverage of this narrow criterion/scope, not media quality or ranking strength. API creation time is not capture date. No ranking score or upload quota.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='command',required=True)
    p=sp.add_parser('prepare');p.add_argument('--profiles',required=True);p.add_argument('--out',required=True);p.add_argument('--entity',action='append')
    for cmd in ['collect-owner','import-api']:
        p=sp.add_parser(cmd);p.add_argument('--resource',required=True);p.add_argument('--entity-id',required=True);p.add_argument('--name',default='');p.add_argument('--out',required=True)
        if cmd=='collect-owner':p.add_argument('--token-env',default='GBP_ACCESS_TOKEN');p.add_argument('--max-pages',type=int,default=20)
        else:p.add_argument('--input',required=True);p.add_argument('--observed-at',required=True)
    p=sp.add_parser('analyze');p.add_argument('--input',required=True,nargs='+');p.add_argument('--as-of',required=True);p.add_argument('--days',type=int,default=90);p.add_argument('--out',required=True)
    a=ap.parse_args()
    if a.command=='prepare':
        profiles=json.loads(pathlib.Path(a.profiles).read_text())
        for e in profiles:
            if a.entity and e['entity_id'] not in a.entity:continue
            if not re.fullmatch(r'[A-Za-z0-9_-]+',e['entity_id']):raise ValueError('Unsafe entity filename')
            save(pathlib.Path(a.out)/(e['entity_id']+'.json'),blank(e))
    elif a.command in ['collect-owner','import-api']:
        entity={'entity_id':a.entity_id,'name':a.name};blocker=None
        if a.command=='collect-owner':
            if not 1<=a.max_pages<=100:raise ValueError('max-pages must be 1..100')
            token=os.environ.get(a.token_env)
            if not token:raise ValueError('Missing access token environment variable; do not paste credentials into chat')
            pages,blocker=collect(a.resource,token,a.max_pages);when=dt.datetime.now(UTC).isoformat()
        else:
            data=json.loads(pathlib.Path(a.input).read_text());pages=data if isinstance(data,list) else [data];when=a.observed_at
        inv=normalize_api(pages,entity,a.resource,when)
        if blocker:inv.update(coverage='sample',collection_state='blocked' if not pages else 'collected',blocker=blocker)
        inv['attempts']=[{'at':when,'method':inv['method'],'result':blocker or 'collected endpoint pages'}]
        out=pathlib.Path(a.out);save(out/'api-response-pages.json',pages);save(out/'inventory.json',inv)
    else:
        if a.days<=0:raise ValueError('days must be positive')
        results=[summarize(json.loads(pathlib.Path(f).read_text()),a.as_of,a.days) for f in a.input]
        out=pathlib.Path(a.out);save(out/'media-audit-results.json',results);save(out/'collection-gaps.json',[g for r in results for g in r['collection_gaps']])
        out.mkdir(parents=True,exist_ok=True)
        with (out/'media-comparison.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['entity_id','name','criterion_id','status','finding','next_step','coverage_scope'])
            for r in results:
                for c in r['checks']:w.writerow([r['entity_id'],r['name'],c['criterion_id'],c['status'],c['finding'],c['next_step'],r['coverage_scope']])
    print('Completed '+a.command)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:print('Error: '+str(e),file=sys.stderr);sys.exit(2)
