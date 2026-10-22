'use strict';
const $=id=>document.getElementById(id), config=window.GBP_AUDIT_CONFIG||{}, hosted=config.hosted===true;
const base=hosted?String(config.apiBase||'/api').replace(/\/$/,''):'http://127.0.0.1:8765';
let token='',bulk=false,connected=false,busy=false,activeJob='',pollTimer=null;
const sessionKey='gbp-audit-session:'+base;
function storeSession(){if(hosted)try{sessionStorage.setItem(sessionKey,token)}catch{}}
function startState(){
 $('start').disabled=!connected||busy||!$('consent').checked;
 $('startHint').textContent=!connected?(hosted?'Connecting to the background audit service…':'Connect the runner in step 1 before starting an audit.'):busy?'Audit running in the background. You can reopen it from Recent audits.':!$('consent').checked?'Tick the required collection approval below to enable the audit button.':'Ready. Complete the required fields, then click Audit & create PowerPoint.';
}
async function api(path,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path.includes('/file/')?120000:hosted&&['/session','/health'].includes(path)?90000:30000);
 try{
  const response=await fetch(base+path,{...options,signal:controller.signal,headers:{'Authorization':'Bearer '+token,...options.headers}});
  if(!response.ok){let detail;try{detail=await response.json()}catch{}const e=Error(detail?.error||detail?.detail||'Request failed ('+response.status+')');e.status=response.status;throw e;}
  // Read downloads before removing the timeout, including the response body.
  if(path.includes('/file/')){const file=await response.blob();return {blob:async()=>file};}
  return response;
 }finally{clearTimeout(timer);}
}
async function refreshHistory(){
 try{
  const result=await(await api('/jobs')).json();$('recentAudits').replaceChildren();$('history').hidden=!result.jobs.length;
  for(const job of result.jobs){
   const b=document.createElement('button');b.type='button';b.textContent=(job.status==='completed'?'Open completed audit':job.status==='failed'?'Open saved audit':'Open running audit')+' · '+job.id.slice(0,8);
   b.onclick=()=>openJob(job.id);$('recentAudits').append(b);
  }
  return result.jobs;
 }catch(e){if(e.status!==404)$('error').textContent='Could not load recent audits. '+e.message;}
}
async function connect(){
 if(!hosted){token=$('token').value.trim();$('token').removeAttribute('aria-invalid');if(!token){connected=false;$('token').setAttribute('aria-invalid','true');$('connection').textContent='Pairing code is required. Start Python runner.py and copy the code printed in its window.';$('token').focus();startState();return;}}
 $('connect').disabled=true;$('connection').textContent=hosted?'Connecting to the background service… Free hosting may need up to 90 seconds to wake up.':'Checking your local runner…';
 try{
  if(hosted&&!token){const r=await(await api('/session',{method:'POST'})).json();token=r.token;storeSession();}
  const health=await(await api('/health')).json(),[major,minor]=String(health.version||'0.0').split('.').map(Number);
  if(!(major>1||(major===1&&minor>=3)))throw Error('Update needed: download the latest project and restart the Python runner.');
  if(hosted&&health.max_media!==undefined)mediaLimit(health.max_media);if(hosted&&health.max_stores)$('bulkLimit').textContent='Hosted limit: '+health.max_stores+' store(s) per job / 3.5 MB file. Reports and screenshots are processed on the hosted service.';connected=true;$('connection').textContent=hosted?'Connected · audits run in the background':'Connected · ready to audit';const recent=await refreshHistory();if(!activeJob)activeJob=(recent||[]).find(j=>['queued','running'].includes(j.status))?.id||'';
  if(activeJob){busy=true;openJob(activeJob);}
 }catch(e){connected=false;$('connection').textContent=hosted?'Background service unavailable. Try again shortly.':e.status===403?'Pairing code rejected. Copy the current code from the running Python window; restarting it creates a new code.':e.message.startsWith('Update needed:')?e.message:'Cannot reach the runner on this computer. Start Python runner.py and keep it open, or use the local interface linked above.';}
 finally{$('connect').disabled=false;startState();}
}
function mediaLimit(limit){for(const option of Array.from($('media').options))if(Number(option.value)>limit)option.remove();if(limit===0){$('media').value='0';$('media').disabled=true;if(!$('freeMediaHint')){const hint=document.createElement('p');hint.id='freeMediaHint';hint.className='hint';hint.textContent='Free hosting: gallery sampling is off to stay within memory limits. Profile and ranking screenshots are still collected; gallery checks remain unmeasured.';$('media').parentElement.append(hint);}}}
$('connect').onclick=connect;$('retryConnection').onclick=connect;$('consent').onchange=startState;
function mode(value){bulk=value;$('singleFields').hidden=bulk;$('bulkFields').hidden=!bulk;for(const e of $('singleFields').querySelectorAll('input'))e.disabled=bulk;$('upload').disabled=!bulk;$('upload').required=bulk;$('error').textContent='';$('singleTab').setAttribute('aria-pressed',!bulk);$('bulkTab').setAttribute('aria-pressed',bulk);}
$('singleTab').onclick=()=>mode(false);$('bulkTab').onclick=()=>mode(true);
const latitude=document.querySelector('[name=search_latitude]'),longitude=document.querySelector('[name=search_longitude]');
function coordinateValidity(){const incomplete=Boolean(latitude.value.trim())!==Boolean(longitude.value.trim());for(const field of [latitude,longitude])field.setCustomValidity(incomplete?'Provide both fallback latitude and longitude, or leave both empty.':'');}
latitude.addEventListener('input',coordinateValidity);longitude.addEventListener('input',coordinateValidity);
$('auditForm').addEventListener('invalid',event=>{const details=event.target.closest('details');if(details)details.open=true;$('error').textContent='Please check the required or highlighted field: '+($('auditForm').querySelector(':invalid')?.closest('label')?.textContent.trim()||event.target.validationMessage);},true);
function file64(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});}
$('auditForm').onsubmit=async event=>{
 event.preventDefault();$('error').textContent='';if(!connected){$('error').textContent='Connect to the audit service first.';return;}if(busy)return;
 try{
  const payload={consent:$('consent').checked,media_limit:Number($('media').value),brand:{client:$('client').value,color:$('color').value,accent:$('accent').value,agency:$('agency').value}};
  const logo=$('logo').files[0];if(logo){if(logo.size>1000000)throw Error('Logo must be below 1 MB');payload.logo=await file64(logo);}
  if(bulk){const f=$('upload').files[0];if(!f)throw Error('Choose a CSV or Excel file');if(f.size>3500000)throw Error('Upload must be below 3.5 MB before encoding');payload.file=await file64(f);payload.extension=f.name.split('.').pop().toLowerCase();}else payload.rows=[Object.fromEntries(new FormData($('auditForm')))];
  const encoded=JSON.stringify(payload);if(new TextEncoder().encode(encoded).length>5000000)throw Error('File and logo together are too large (5 MB request limit).');
  busy=true;startState();const job=await(await api('/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:encoded})).json();await openJob(job.id);refreshHistory();
 }catch(e){$('error').textContent=e.name==='AbortError'?'Request timed out. Check Recent audits before retrying; the job may already have started.':e.message;busy=false;startState();}
};
async function download(id,file,button){
 const label=button.textContent;button.disabled=true;button.textContent='Preparing download…';$('exportStatus').textContent='';
 try{
  const response=await api('/jobs/'+id+'/file/'+encodeURIComponent(file)),blob=await response.blob();
  if(blob.size===0)throw Error('The exported file is empty. Click Rebuild PowerPoint to try again from saved data.');
  const bytes=new Uint8Array(await blob.slice(0,4).arrayBuffer());if(bytes[0]!==80||bytes[1]!==75)throw Error('The response is not a valid PowerPoint/ZIP file. Reopen the audit and rebuild its reports.');
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=file.split('/').pop();document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  $('exportStatus').textContent='Download sent to your browser. Check Downloads. If it was blocked, allow downloads for this site and try again.';
 }catch(e){$('exportStatus').textContent='Download failed: '+(e.name==='AbortError'?'The file transfer timed out. Try again.':e.message);}
 finally{button.disabled=false;button.textContent=label;}
}
async function openJob(id){clearTimeout(pollTimer);activeJob=id;$('results').hidden=false;$('downloads').replaceChildren();$('exportStatus').textContent='';await poll(id);}
async function poll(id){
 if(activeJob!==id)return;
 try{
  const job=await(await api('/jobs/'+id)).json();if(activeJob!==id)return;
  const terminal=['completed','failed'].includes(job.status);busy=!terminal;startState();
  $('jobStatus').textContent=job.status==='completed'?'Audit complete · reports ready':job.status==='failed'?'Audit stopped · saved files below':job.status==='queued'?'Audit queued':'Audit in progress';$('log').textContent=job.messages.join('\n');
  $('downloads').replaceChildren();$('rebuild').hidden=!terminal;
  if(terminal){
   for(const file of job.files){if(!file.endsWith('.pptx')&&!file.endsWith('.zip'))continue;const b=document.createElement('button');b.type='button';b.textContent=file.endsWith('.zip')?'Download all evidence ↓':file.startsWith('all-stores-')?'Download all stores PowerPoint ↓':'Download '+file.split('/')[0].split('-')[0]+' PowerPoint ↓';b.onclick=()=>download(id,file,b);$('downloads').append(b);}
   refreshHistory();return;
  }
  pollTimer=setTimeout(()=>poll(id),2500);
 }catch(e){busy=false;if(e.status===404){activeJob='';connected=true;$('jobStatus').textContent='Audit unavailable · job expired or service restarted';$('error').textContent='This saved job is no longer available. Free hosting can lose jobs on restart. You can start a new audit.';$('rebuild').hidden=true;refreshHistory();}else{connected=false;$('connection').textContent='Connection lost. Reconnect to recover audit progress.';$('error').textContent='Progress could not be loaded. Reconnect or reopen the app and use Recent audits. Do not start a duplicate job.';}startState();}
}
$('rebuild').onclick=async()=>{
 if(!activeJob)return;$('rebuild').disabled=true;$('exportStatus').textContent='Rebuilding reports from saved data…';
 try{await api('/jobs/'+activeJob+'/export',{method:'POST'});await openJob(activeJob);}
 catch(e){$('exportStatus').textContent='Could not rebuild: '+e.message;}
 finally{$('rebuild').disabled=false;}
};
if(hosted){
 try{token=sessionStorage.getItem(sessionKey)||'';}catch{}
 $('setupIntro').innerHTML='<span class="step">01 / READY</span><h2>Your audit runs in the background</h2><p>No Python, extensions or local setup. Enter your store link and keyword below. Reopen audits from Recent audits in this browser tab. Download reports you want to keep. Reports may expire or be lost when a free service restarts.</p>';
 for(const element of [$('token'),$('connect'),document.querySelector('label[for=token]')])element.hidden=true;
 $('retryConnection').hidden=false;mediaLimit(config.maxMedia??20);
 $('bulkLimit').textContent='Hosted limit: '+(config.maxStores||10)+' store(s) per job / 3.5 MB file. Reports and screenshots are processed on the hosted service.';
 $('consentText').textContent='I approve public browser collection and screenshots on the hosted service. This does not edit profiles or bypass access blocks.';
 $('resultHelp').textContent='Collection and PowerPoint generation run automatically in the background. Reopen this app in the same tab and use Recent audits to recover progress and downloads. Download files promptly; on free hosting they can be lost after a restart.';
 startState();connect();
}
