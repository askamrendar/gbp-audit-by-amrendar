"""Editable agency-style report; all conclusions retain collection limits."""
import pathlib,re
from collections import Counter
from urllib.parse import urlparse

def website_facts(w):
 if not w or w.get('error'):return {'Destination':w.get('error','No inspected GBP-linked page') if w else 'No inspected GBP-linked page'}
 types=[]
 def walk(v):
  if isinstance(v,dict):
   t=v.get('@type',[]);types.extend(t if isinstance(t,list) else [t]);[walk(x) for x in v.values()]
  elif isinstance(v,list):[walk(x) for x in v]
 for block in w.get('schema',[]):walk(block.get('value'))
 frames=w.get('iframes',[]);social=[x for x in frames if re.search('instagram|facebook|tiktok|youtube',x.get('src',''),re.I)];maps=[x for x in frames if re.search('google.+maps',x.get('src',''),re.I)]
 return {'Destination':w.get('page_type','Unknown')+' · '+w.get('url',w.get('requested_url','')),'Title / local intent':w.get('title') or 'No title captured','Headings / layout':' | '.join(x.get('text','') for x in w.get('headings',[])[:3]) or 'No visible headings captured','Schema types':', '.join(dict.fromkeys(str(x) for x in types if x)) or 'No types parsed; confirm other markup formats','JSON-LD syntax':str(sum(x.get('syntax')=='invalid' for x in w.get('schema',[])))+' invalid blocks / '+str(len(w.get('schema',[])))+' inspected','Map embed':str(len(maps))+' iframe candidates; branch match needs review','Social embed':str(len(social))+' iframe candidates; rendered content needs review','Review embed':'Not established by iframe inventory; inspect rendered page/widgets','Content / conversion':'Branch address, hours, useful copy and CTA need comparison to approved facts'}

def form_values(p,keyword):
 body=p.get('body','');g=p.get('gallery',{});items=g.get('items',[]);w=p.get('website_audit',{});name=p.get('name','Unknown')
 return [name,(p.get('address') or 'Address not exposed')+' / '+(p.get('phone') or 'Phone not exposed'), 'Displayed name: '+name+'; no keyword-only name additions', 'Verify locality wording against real signage',p.get('website') or ('No link · Add website observed' if p.get('website_link_state')=='missing' else 'Not exposed'),p.get('category') or 'Primary / additional categories not established', 'Expanded weekly schedule captured; verify special hours' if p.get('hours_evidence') else 'Full weekly schedule not captured', 'About evidence captured; inspect payment attributes' if p.get('about_evidence') else 'Payment methods not established',p.get('description') or 'Description not established',p.get('reviews_summary') or 'Review/reply period and denominator not measured', 'Post captured; inspect dated content and CTA' if p.get('post_evidence') else 'Published posts not established','Review actual captured GBP description/posts', 'Action-link availability and journey need review',w.get('page_type','No inspected destination')+'; branch identity needs review',p.get('entity_id') or 'Exact ID unresolved','Current Q&A availability / answers not established',str(len(items))+' gallery items captured (sample)', '30/90-day owner uploads unknown; sample is not full history', ', '.join(sorted({x.get('image_type') for x in items if x.get('image_type')})) or 'Captured images need visual classification',str(sum(x.get('format')=='video' for x in items))+' video labels in sample; content review pending',website_facts(w).get('Map embed','No inspected linked-page map')]

FORM=['Business name','Address / phone','Keyword in name','Locality in name','GBP website link','Categories','Full opening hours','Payment attributes','Description','Review replies','Published posts','Copy / content type','Action links','Branch deep link','Profile identifier','Q&A availability','Gallery presence','Upload recency / quantity','Image types','Videos','Website map']

def export_ppt(data,path):
 from pptx import Presentation
 from pptx.util import Inches,Pt
 from pptx.dml.color import RGBColor
 from PIL import Image
 r=Presentation();r.slide_width=Inches(13.333);r.slide_height=Inches(7.5)
 brand=data.get('brand') or {};raw=brand.get('color','#133b36').lstrip('#');raw=raw if re.fullmatch('[a-fA-F0-9]{6}',raw) else '133b36';ink=RGBColor.from_string(raw.upper());muted=RGBColor(86,104,100)
 profiles=data['profiles'];target=profiles[0];rank=data.get('ranking',{});keyword=data['input']['keyword'];names=[p.get('name') or 'Unresolved' for p in profiles];names[0]+=' ('+data['input']['store_code']+')'
 def text(s,value,x,y,w,h,size=18,color=None,bold=False):
  t=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));t.text_frame.word_wrap=True
  t.text_frame.text=str(value)
  for p in t.text_frame.paragraphs:p.font.name='Aptos';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=color or ink
  return t
 def slide(title,sub=None):
  s=r.slides.add_slide(r.slide_layouts[6]);text(s,f'{len(r.slides):02d}',12.1,.35,.6,.4,12,muted);text(s,title,.55,.42,11.5,.6,27,bold=True)
  if sub:text(s,sub,.58,1.12,12.1,.65,12,muted)
  return s
 def img(s,file,x,y,w,h):
  if not file or not pathlib.Path(file).is_file():text(s,'Screenshot unavailable · see collection log',x,y,w,h,15,muted);return
  with Image.open(file) as im:ratio=im.width/im.height
  nw=min(w,h*ratio);nh=nw/ratio;s.shapes.add_picture(str(file),Inches(x+(w-nw)/2),Inches(y+(h-nh)/2),width=Inches(nw),height=Inches(nh))
 def table(s,headers,rows,y=1.95,height=4.7):
  shape=s.shapes.add_table(len(rows)+1,len(headers),Inches(.58),Inches(y),Inches(12.15),Inches(height));tab=shape.table
  tab.columns[0].width=Inches(2.1)
  for col in list(tab.columns)[1:]:col.width=Inches(10.05/(len(headers)-1))
  for i,row in enumerate([headers]+rows):
   for j,value in enumerate(row):
    cell=tab.cell(i,j);cell.text=(str(value)[:107]+'…') if len(str(value))>110 else str(value);cell.margin_left=cell.margin_right=Inches(.1);cell.margin_top=Inches(.035);cell.margin_bottom=Inches(.025);cell.fill.solid();cell.fill.fore_color.rgb=ink if i==0 else RGBColor(*( (242,246,242) if i%2 else (255,255,255)))
    for p in cell.text_frame.paragraphs:p.font.name='Aptos';p.font.size=Pt(11 if len(headers)<=3 else 10.5);p.font.bold=i==0 or j==0;p.font.color.rgb=RGBColor(255,255,255) if i==0 else ink
  s.notes_slide.notes_text_frame.text='Full comparison values:\n'+'\n'.join(' | '.join(map(str,row)) for row in [headers]+rows)+'\nSource: audit.json and form-comparison.csv; no assumed failures.'
  return tab
 def notes(s,value):s.notes_slide.notes_text_frame.text=value
 s=slide(brand.get('client') or target.get('name') or data['input']['store_code']);text(s,'Local visibility & competitor audit',.6,2,11,1.2,38,bold=True);text(s,keyword,.65,3.5,11,.8,25);text(s,'Evidence collected '+data['started_at'][:10]+'\nPublic evidence report · owner and visual checks remain open',.65,5.2,11,1,16,muted)
 s=slide('Profile and keyword visibility','Authentic browser captures · full captured view retained without cropping');img(s,target.get('screenshot'),.6,1.8,6,4.65);img(s,rank.get('screenshot'),6.8,1.8,5.9,4.65)
 pos=next((x['position'] for x in rank.get('results',[]) if x.get('entity_id')==target.get('entity_id') and target.get('entity_id')),None)
 text(s,('Observed target position: '+str(pos) if pos else 'Target position not established in loaded results')+' · exploratory Maps area view; physical customer origin unverified',.6,6.65,12,.4,12,muted);notes(s,json_sources(data))
 s=slide('The local comparison','Competitors come from the observed keyword results. A ranking observation does not prove causation.')
 table(s,['Profile','Role / observed order','Website / collection'],[[names[i],('Target · '+str(next((x['position'] for x in rank.get('results',[]) if x.get('entity_id')==p.get('entity_id') and p.get('entity_id')), 'not in loaded results'))) if i==0 else 'Observed order '+str(next((x['position'] for x in rank.get('results',[]) if x.get('entity_id')==p.get('entity_id') and p.get('entity_id')), 'unresolved')),p.get('website') or p.get('blocker') or 'Website link not exposed / missing; see checklist'] for i,p in enumerate(profiles)],height=3.8)
 text(s,'Search centre: '+str(rank.get('requested_center','Unresolved'))+' ('+str((data.get('search_location') or {}).get('source','unresolved'))+')'+' · '+str(rank.get('blocker') or rank.get('sponsored_exclusion','Review screenshot and identity matches before accepting order.')),.6,6,12,.7,13,muted)
 counts=Counter(c['status'] for c in target.get('checks',[]));fails=[c for c in target.get('checks',[]) if c['status']=='Fail'];partials=[c for c in target.get('checks',[]) if c['status']=='Partial']
 s=slide('What needs attention','Fail = evidenced problem · Partial = some evidence, acceptance incomplete · Unknown = not established · NA requires a reason')
 text(s,' · '.join(f'{k}: {v}' for k,v in counts.items()),.6,1.85,12,.55,20,bold=True)
 rows=[[c['check'],c['finding'],c.get('next_input','')] for c in (fails+partials)[:5]] or [['Evidence gap','Collection did not establish actionable profile findings','Resolve access or identity and repeat affected checks']]
 table(s,['Check','Evidence / implication','Next action'],rows,y=2.6,height=3.8)
 vals=[form_values(p,keyword) for p in profiles]
 for start in [0,7,14]:
  s=slide(['Profile fundamentals','Content and customer journey','Identity and media'][start//7],'Equivalent evidence rules apply to the target and each competitor. Unobserved fields remain unresolved.')
  table(s,['Criterion']+names,[[FORM[i]]+[v[i] for v in vals] for i in range(start,min(start+7,21))],height=4.9)
 s=slide('Media evidence and practical gaps','Observed items are a sample. A gallery total cannot establish upload frequency or ownership.')
 table(s,['Profile','Sample evidence','Gap / completion step'],[[names[i],str(len(p.get('gallery',{}).get('items',[])))+' captured · '+str(sum(x.get('format')=='video' for x in p.get('gallery',{}).get('items',[])))+' video labels',str(p.get('gallery',{}).get('blocker') or 'Gallery not inspected')+' · Review entrance, interior, products and relevance; verify dated owner history separately.'] for i,p in enumerate(profiles)],height=4.4)
 facts=[website_facts(p.get('website_audit',{})) for p in profiles]
 for title,fields in [('Linked page: relevance and layout',['Destination','Title / local intent','Headings / layout','Content / conversion']),('Linked page: schema and embedded content',['Schema types','JSON-LD syntax','Map embed','Social embed','Review embed'])]:
  s=slide(title,'Actual GBP-linked destination only; supplementary discovered pages are retained separately in audit.json.')
  table(s,['Check']+names,[[f]+[w.get(f,'Not established') for w in facts] for f in fields],height=4.8)
 s=slide('Prioritised improvement plan','Recommendations are evidence-led. No profile edits or website publishing have been performed.')
 tasks=[]
 for c in fails[:2]:tasks.append(['Now',c['check']+': '+c['finding'],c.get('next_input','Verify corrected public result')])
 tasks += [['Next','Confirm target branch, contact details and correct location URL','Approved store facts match GBP and linked page'],['Next','Review local page content, useful arrival information and schema','Branch facts and visible markup agree; fix evidenced issues'],['Measure','Repeat keyword observations from agreed customer locations','Record origin, date, surface and sponsored exclusions'],['Complete','Review gallery content and remaining owner-only evidence','Resolve checklist gaps using dated evidence, not assumed failures']]
 table(s,['Priority','Work item','Acceptance check'],tasks[:6],height=4.75)
 for s in r.slides:
  if not s.notes_slide.notes_text_frame.text.strip():notes(s,'Source: local audit.json, checklist.csv and evidence artifacts. Unknown is not failure. Full 70-check detail is in CSV. No invented rank, image classification or private account data.')
 r.save(path)

def json_sources(data):
 return 'Target: '+str(data['profiles'][0].get('url'))+'\nRanking: '+str(data.get('ranking',{}).get('url'))+'\nCollected: '+data['started_at']+'\nMethod: exploratory Maps area view. Review loaded order, exclusions and exact profile IDs.'
