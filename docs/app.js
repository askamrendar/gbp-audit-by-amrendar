'use strict';
const $=id=>document.getElementById(id), base='http://127.0.0.1:8765';
let token='',bulk=false,connected=false;
let busy=false,activeJob='';
function startState(){
 $('start').disabled=!connected||busy||!$('consent').checked;
 $('startHint').textContent=!connected?'Connect the runner in step 1 before starting an audit.':busy?'Audit running. Keep the runner and its Chrome window open.':!$('consent').checked?'Tick the required collection approval below to enable the audit button.':'Ready. Complete the required fields, then click Audit & create PowerPoint.';
}
async function api(path,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try{
  const response=await fetch(base+path,{...options,signal:controller.signal,headers:{'Authorization':'Bearer '+token,...options.headers}});
  if(!response.ok){let detail;try{detail=await response.json()}catch{}const e=Error(detail?.error||'Runner request failed');e.status=response.status;throw e;}
  return response;
 }finally{clearTimeout(timer);}
}
$('consent').onchange=startState;
$('connect').onclick=async()=>{
 token=$('token').value.trim();$('token').removeAttribute('aria-invalid');
 if(!token){connected=false;$('token').setAttribute('aria-invalid','true');$('connection').textContent='Pairing code is required. Start Python runner.py and copy the code printed in its window.';$('token').focus();startState();return;}
 $('connect').disabled=true;$('connection').textContent='Checking your local runner…';
 try{
  const health=await(await api('/health')).json(),[major,minor]=String(health.version||'0.0').split('.').map(Number);
  if(!(major>1||(major===1&&minor>=2)))throw Error('Update needed: download the latest project and restart the Python runner.');
  connected=true;$('connection').textContent='Connected · ready to audit';if(activeJob){busy=true;poll(activeJob);}
 }catch(e){
  connected=false;
  $('connection').textContent=e.status===403?'Pairing code rejected. Copy the current code from the running Python window; restarting it creates a new code.':e.message.startsWith('Update needed:')?e.message:'Cannot reach the runner on this computer. Start Python runner.py and keep its window open. If it is already running, allow local network access when Chrome asks, or use the local interface linked above.';
 }finally{$('connect').disabled=false;startState();}
};
function mode(value){bulk=value;$('singleFields').hidden=bulk;$('bulkFields').hidden=!bulk;for(const e of $('singleFields').querySelectorAll('input'))e.disabled=bulk;$('upload').disabled=!bulk;$('upload').required=bulk;$('error').textContent='';$('singleTab').setAttribute('aria-pressed',!bulk);$('bulkTab').setAttribute('aria-pressed',bulk);}
$('singleTab').onclick=()=>mode(false);$('bulkTab').onclick=()=>mode(true);
const latitude=document.querySelector('[name=search_latitude]'),longitude=document.querySelector('[name=search_longitude]');
function coordinateValidity(){const incomplete=Boolean(latitude.value.trim())!==Boolean(longitude.value.trim());latitude.setCustomValidity(incomplete?'Provide both fallback latitude and longitude, or leave both empty.':'');longitude.setCustomValidity(incomplete?'Provide both fallback latitude and longitude, or leave both empty.':'');}
latitude.addEventListener('input',coordinateValidity);longitude.addEventListener('input',coordinateValidity);
$('auditForm').addEventListener('invalid',event=>{const details=event.target.closest('details');if(details)details.open=true;$('error').textContent='Please check the required or highlighted field: '+($('auditForm').querySelector(':invalid')?.closest('label')?.textContent.trim()||event.target.validationMessage);},true);
function file64(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});}
$('auditForm').onsubmit=async event=>{event.preventDefault();$('error').textContent='';if(!connected){$('error').textContent='Connect the runner in step 1 first.';return;}if(busy)return;try{const payload={consent:$('consent').checked,media_limit:Number($('media').value),brand:{client:$('client').value,color:$('color').value,accent:$('accent').value,agency:$('agency').value}};
const logo=$('logo').files[0];if(logo){if(logo.size>1000000)throw Error('Logo must be below 1 MB');payload.logo=await file64(logo);}
if(bulk){const f=$('upload').files[0];if(!f)throw Error('Choose a CSV or Excel file');if(f.size>3500000)throw Error('Upload must be below 3.5 MB before encoding');payload.file=await file64(f);payload.extension=f.name.split('.').pop().toLowerCase();}else payload.rows=[Object.fromEntries(new FormData($('auditForm')))];
const encoded=JSON.stringify(payload);if(new TextEncoder().encode(encoded).length>5000000)throw Error('File and logo together are too large. Use a smaller file or logo (5 MB request limit).');busy=true;startState();const job=await(await api('/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:encoded})).json();$('results').hidden=false;$('downloads').replaceChildren();activeJob=job.id;poll(job.id);
}catch(e){$('error').textContent=e.name==='AbortError'?'Runner request timed out. Check that its window is open.':e.message;busy=false;startState();}};
async function poll(id){try{const job=await(await api('/jobs/'+id)).json();$('jobStatus').textContent=job.status==='completed'?'Audit complete · PowerPoint ready':job.status==='failed'?'Audit stopped · check the collection log':'Audit in progress';$('log').textContent=job.messages.join('\n');if(['completed','failed'].includes(job.status)){busy=false;activeJob='';startState();for(const file of job.files){if(!file.endsWith('.pptx')&&!file.endsWith('.zip'))continue;const b=document.createElement('button');b.textContent=file.endsWith('.zip')?'Download all evidence ↓':(file.startsWith('all-stores-')?'Download all stores PowerPoint ↓':'Download '+file.split('/')[0]+' PowerPoint ↓');b.onclick=async()=>{try{const blob=await(await api('/jobs/'+id+'/file/'+encodeURIComponent(file))).blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=file.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){$('error').textContent=e.message;}};$('downloads').append(b);}return;}setTimeout(()=>poll(id),2000);}catch(e){connected=false;busy=false;$('connection').textContent='Connection lost. Reconnect using the current pairing code.';$('error').textContent='Unable to read audit progress. Keep the runner open and reconnect; do not start a duplicate audit while the current one is running.';startState();}}
