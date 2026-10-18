let job = null, result = null, savedReview = null;
const $ = id => document.getElementById(id);
async function api(path, data) {
  const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const value = await response.json(); if (!response.ok) throw Error(value.error); return value;
}
async function get(path) {const response=await fetch(path);const value=await response.json();if(!response.ok)throw Error(value.error);return value;}
function status(message) {$('status').textContent=message;}
function option(value,label) {const item=document.createElement('option');item.value=value;item.textContent=label;return item;}
function show(id,box) {
  const page=result.pages.find(p=>p.id===id);if(!page)return;
  $('pages').value=id;$('page').src='/image/'+job+'/'+page.image;$('ocr').textContent=page.ocr.text;
  $('page-caption').textContent=page.file+' · page '+page.number+' · '+page.kind;
  $('highlight').hidden=!box;
  if(box){const [x,y,w,h]=box;Object.assign($('highlight').style,{left:100*x/page.size[0]+'%',top:100*y/page.size[1]+'%',width:100*w/page.size[0]+'%',height:100*h/page.size[1]+'%'});}
}
function documentResolutions() {return [...$('findings').children].map((row,index)=>({id:String(index),resolution:row.querySelector('select').value,note:row.querySelector('textarea').value}));}
function display() {
  $('pages').replaceChildren();$('findings').replaceChildren();
  result.pages.forEach(p=>$('pages').append(option(p.id,p.file+' · page '+p.number+' · '+p.kind)));
  result.findings.forEach((finding,index)=>{
    const row=document.createElement('div');row.className='finding';
    const title=document.createElement('strong');title.textContent=finding[0]+' | '+finding[1];row.append(title);
    const button=document.createElement('button');button.textContent='View evidence';button.onclick=()=>{if(finding[3])show(finding[3]);$('evidence').textContent=finding[2];};row.append(document.createElement('br'),button);
    const label=document.createElement('label');label.textContent='Resolution ';const resolution=document.createElement('select');resolution.setAttribute('aria-label','Finding '+(index+1)+' resolution');
    ['Unresolved','Confirmed','Not applicable','Discrepancy'].forEach(v=>resolution.append(option(v,v)));label.append(resolution);row.append(label);
    const note=document.createElement('textarea');note.placeholder='Evidence checked / justification';note.setAttribute('aria-label','Finding '+(index+1)+' note');row.append(note);
    const previous=savedReview?.resolutions?.find(r=>r.id===String(index));if(previous){resolution.value=previous.resolution;note.value=previous.note;}
    $('findings').append(row);
  });
  if(result.pages.length)show(result.pages[0].id);
  materialControls();$('name').value=savedReview?.inspector||'';$('notes').value=savedReview?.notes||'';$('decision').value=savedReview?.decision||'Needs review';
  $('export').hidden=false;$('export').href='/case/'+job+'/export';
}
async function openCase(id) {
  if(!id)return;job=id;result=null;savedReview=null;
  $('material-observations').replaceChildren();$('material-results').textContent='';$('findings').replaceChildren();$('export').hidden=true;
  while(true){if(job!==id)return;const state=await get('/job/'+id);if(job!==id)return;status(state.progress||state.state);
    if(state.state==='error')throw Error(state.error);
    if(state.state==='done'){result=state.result;savedReview=state.review||null;display();status(result.pages.length+' pages · '+result.findings.length+' findings · '+(savedReview?.decision||'Needs inspector review'));break;}
    await new Promise(resolve=>setTimeout(resolve,1200));
  }
}
async function refreshCases() {
  const current=$('cases').value;const cases=await get('/cases');$('cases').replaceChildren(option('','Choose case'));
  cases.forEach(c=>$('cases').append(option(c.id,c.created.slice(0,16)+' · '+c.files.join(', ')+' · '+(c.decision||c.state))));$('cases').value=current;
  const inbox=await get('/inbox');$('inbox-status').textContent=inbox.batches.map(b=>b.batch+': '+(b.error||b.state)).join(' | ');
}
$('pages').onchange=()=>show($('pages').value);
$('refresh-cases').onclick=()=>refreshCases().catch(e=>status(e.message));
$('open-case').onclick=()=>openCase($('cases').value).catch(e=>status(e.message));
$('run').onclick=async()=>{
  try{const files=[...$('files').files];if(!files.length)throw Error('Select PDFs first');$('run').disabled=true;
    const payload=[];for(const file of files){const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});payload.push({name:file.name,data});}
    const ids=[...$('specs').selectedOptions].map(o=>o.value);const created=await api('/inspect',{files:payload,specification_ids:ids});await openCase(created.job);await refreshCases();
  }catch(error){status(error.message);}finally{$('run').disabled=false;}
};
$('save').onclick=async()=>{
  try{if(!result)throw Error('Complete inspection first');const saved=await api('/review',{job,inspector:$('name').value,decision:$('decision').value,notes:$('notes').value,observations:observations(),resolutions:documentResolutions()});savedReview=saved.review;status('Review saved: '+saved.saved);await refreshCases();}
  catch(error){status(error.message);}
};
get('/registry').then(data=>data.specs.filter(s=>s.status==='Approved').forEach(s=>$('specs').append(option(s.id,s.code+' rev '+s.revision+' · '+s.applicability+' (ID '+s.id+')')))).catch(error=>status(error.message));
refreshCases().catch(error=>status(error.message));setInterval(()=>refreshCases().catch(()=>{}),8000);
