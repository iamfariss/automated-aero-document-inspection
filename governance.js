const $=id=>document.getElementById(id);let token='';let catalogueSource=null,catalogueOffset=0;
function message(value){$('status').textContent=value;}
async function action(fn){try{await fn();}catch(error){message(error.message);}}
async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw Error(value.error);return value;}
function ruleRow(){const row=document.createElement('fieldset');const legend=document.createElement('legend');legend.textContent='Requirement';row.append(legend);for(const [key,label] of [['property','Property name'],['unit','Unit'],['condition','Material condition'],['clause','Source page / clause'],['min','Minimum'],['max','Maximum'],['aliases','OCR aliases, comma separated']]){const wrapper=document.createElement('label');wrapper.textContent=label;const input=document.createElement('input');input.dataset.key=key;if(key==='min'||key==='max')input.inputMode='decimal';wrapper.append(input);row.append(wrapper);}const remove=document.createElement('button');remove.textContent='Remove requirement';remove.onclick=()=>row.remove();row.append(remove);$('rules').append(row);}
async function refresh(){const d=await(await fetch('/registry')).json();$('setup').hidden=d.configured;$('rows').replaceChildren();$('profile-specs').replaceChildren();d.specs.filter(s=>s.status==='Approved').forEach(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.code+' revision '+s.revision+' (ID '+s.id+')';$('profile-specs').append(o);});fetch('/scanner-profiles').then(r=>r.json()).then(p=>$('profiles').textContent=JSON.stringify(p,null,2));d.specs.forEach(spec=>{const row=document.createElement('tr');[spec.id+' · '+spec.code,spec.revision,spec.applicability,spec.status].forEach(value=>{const cell=document.createElement('td');cell.textContent=value;row.append(cell);});const evidence=document.createElement('td');const pdf=document.createElement('a');pdf.href='/specification/'+spec.id;pdf.target='_blank';pdf.rel='noopener';pdf.textContent='Open source PDF';evidence.append(pdf);const detail=document.createElement('button');detail.textContent='Details';detail.onclick=()=>{$('registry-details').textContent=JSON.stringify(spec,null,2);};evidence.append(detail);row.append(evidence);const actions=document.createElement('td');if(token){(spec.status==='Draft'?['approve','reject']:spec.status==='Approved'?['withdraw']:[]).forEach(verb=>{const button=document.createElement('button');button.textContent=verb;button.onclick=()=>action(async()=>{const reason=prompt('Record the evidence reviewed and reason. Approval confirms the source PDF, revision, applicability and every transcribed requirement.');if(!reason)return;await post('/specification/transition',{id:spec.id,action:verb,reason});message('Admin action recorded');await refresh();});actions.append(button);});}row.append(actions);$('rows').append(row);});}
$('add-rule').onclick=ruleRow;
$('create-admin').onclick=()=>action(async()=>{await post('/admin/setup',{name:$('admin-name').value,password:$('password').value});$('password').value='';message('Admin created. Log in to approve specifications.');await refresh();});
$('login').onclick=()=>action(async()=>{const data=await post('/admin/login',{password:$('password').value});token=data.token;$('password').value='';$('who').textContent='Admin: '+data.name+' · expires after 30 minutes';message('Admin logged in');await refresh();});
$('logout').onclick=()=>action(async()=>{await post('/admin/logout',{});token='';$('who').textContent='Inspector access';await refresh();});
$('change-password').onclick=()=>action(async()=>{await post('/admin/password',{old_password:$('password').value,new_password:$('new-password').value});token='';$('password').value='';$('new-password').value='';$('who').textContent='Inspector access';message('Password changed; all sessions revoked. Log in again.');await refresh();});
$('upload').onclick=()=>action(async()=>{const file=$('pdf').files[0];if(!file&&!catalogueSource)throw Error('Choose a specification PDF or catalogue source');const rules=[...$('rules').children].map(row=>{const r={};row.querySelectorAll('input').forEach(input=>{const key=input.dataset.key,value=input.value.trim();if(key==='min'||key==='max'){if(value!==''&&!Number.isFinite(Number(value)))throw Error('Limits must be finite numbers');r[key]=value===''?null:Number(value);}else if(key==='aliases')r.aliases=value?value.split(',').map(x=>x.trim()).filter(Boolean):[];else r[key]=value;});return r;});const data=catalogueSource?null:await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});await post(catalogueSource?'/catalogue/draft':'/specification/upload',{source_id:catalogueSource?.id,code:$('code').value,revision:$('revision').value,title:$('title').value,applicability:$('applicability').value,effective_date:$('effective').value,uploaded_by:$('uploader').value,filename:file?.name,data,rules,material_required:$('material-required').checked});message('Draft submitted. Admin review and approval are required before use.');await refresh();});
$('refresh').onclick=()=>action(refresh);$('audit').onclick=()=>action(async()=>{const response=await fetch('/registry/audit',{headers:{Authorization:'Bearer '+token}});const value=await response.json();if(!response.ok)throw Error(value.error);$('history').textContent=JSON.stringify(value,null,2);});action(refresh);

$('save-profile').onclick=()=>action(async()=>{await post('/scanner-profile',{name:$('profile-name').value,description:$('profile-description').value,specification_ids:[...$('profile-specs').selectedOptions].map(o=>o.value)});message('Scanner profile saved and audited');await refresh();});

fetch('/local-model').then(r=>r.json()).then(c=>{$('lm-enabled').checked=c.enabled;$('lm-model').value=c.model;}).catch(e=>message(e.message));
$('lm-save').onclick=()=>action(async()=>{await post('/local-model/configure',{enabled:$('lm-enabled').checked,model:$('lm-model').value});message('Local model configuration saved and recorded');});

$('lm-check').onclick=()=>action(async()=>{const state=await post('/local-model/check',{});$('lm-status').textContent=JSON.stringify(state,null,2);});

async function catalogueSearch(){
 const response=await fetch('/catalogue/search?q='+encodeURIComponent($('catalogue-query').value)+'&offset='+catalogueOffset);
 const data=await response.json();if(!response.ok)throw Error(data.error);
 $('catalogue-summary').textContent=`${data.total} results. Showing ${data.items.length?catalogueOffset+1:0}–${catalogueOffset+data.items.length}. ${data.scope}`;
 $('catalogue-prev').disabled=catalogueOffset===0;$('catalogue-next').disabled=catalogueOffset+30>=data.total;
 $('catalogue-results').replaceChildren();
 data.items.forEach(source=>{
   const row=document.createElement('div');row.className='finding';
   const name=document.createElement('strong');name.textContent=source.member;row.append(name);
   const info=document.createElement('p');info.textContent=`${source.status} · ${source.pages??'?'} pages · ${source.indexed_pages??0} indexed pages`;row.append(info);
   const excerpt=document.createElement('pre');excerpt.textContent=source.excerpt||source.detail;row.append(excerpt);
   if(source.extension==='.pdf'&&source.status!=='Invalid PDF header'){
     const link=document.createElement('a');link.textContent='Open local source PDF';link.href='/catalogue/pdf/'+source.id;link.target='_blank';link.rel='noopener';row.append(link);
     const button=document.createElement('button');button.textContent='Select source for draft';button.onclick=()=>{catalogueSource=source;$('catalogue-selection').textContent='Selected: '+source.member+' — metadata and rules below must be verified manually.';$('pdf').disabled=true;message('Complete specification metadata and requirements, then Submit draft as admin.');};row.append(button);
   }
   $('catalogue-results').append(row);
 });
}
$('catalogue-search').onclick=()=>action(async()=>{catalogueOffset=0;await catalogueSearch();});
$('catalogue-prev').onclick=()=>action(async()=>{catalogueOffset=Math.max(0,catalogueOffset-30);await catalogueSearch();});
$('catalogue-next').onclick=()=>action(async()=>{catalogueOffset+=30;await catalogueSearch();});
$('catalogue-clear').onclick=()=>{catalogueSource=null;$('pdf').disabled=false;$('catalogue-selection').textContent='Manual PDF upload selected';};
action(catalogueSearch);
