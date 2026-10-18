/* OCR candidates are suggestions; inspector verification is always explicit. */

function materialControls() {

  const host=$('material-observations');host.replaceChildren();$('material-results').textContent='';

  const spec=result.specification;

  $('material-spec').textContent=spec?`${spec.code} revisions ${spec.revision}`:'No approved specifications selected.';

  const rules=spec?.rules||[];

  if(!rules.length){host.textContent=spec?.material_required===false?'Approved document-only scope. Resolve all document findings.':'No approved numerical requirements. Material compliance remains Needs review.';return;}

  rules.forEach((rule,index)=>{

    const group=document.createElement('div');host.append(group);

    const previous=savedReview?.observations?.filter(o=>(rule.rule_id?o.rule_id===rule.rule_id:o.property===rule.property))||[];

    if(previous.length)previous.forEach(o=>materialRow(group,rule,index,o));else materialRow(group,rule,index);

    const add=document.createElement('button');add.textContent='Add another heat: '+rule.property;add.onclick=()=>materialRow(group,rule,index);group.append(add);

  });

  if(savedReview?.property_results)$('material-results').textContent=savedReview.property_results.map(r=>`${r.property||'Material'} / ${r.heat||'unlinked'}: ${r.status}\n${r.reason}`).join('\n\n');

}

function materialRow(group,rule,index,previous) {

  const fieldset=document.createElement('fieldset');fieldset.dataset.property=rule.property;fieldset.dataset.rule=rule.rule_id||'';

  const legend=document.createElement('legend');legend.textContent=`${rule.property} · ${rule.clause} · ${rule.specification_code||''}`;fieldset.append(legend);

  const requirement=document.createElement('p');requirement.textContent=`Approved condition: ${rule.condition}. Limits: ${rule.min??'no minimum'} to ${rule.max??'no maximum'} ${rule.unit} (inclusive).`;fieldset.append(requirement);

  const candidates=(result.candidates||[]).filter(c=>(rule.rule_id?c.rule_id===rule.rule_id:c.property===rule.property));

  const candidateLabel=document.createElement('label');candidateLabel.textContent='OCR candidate ';const picker=document.createElement('select');picker.setAttribute('aria-label',rule.property+' OCR candidate');picker.append(option('','Choose a candidate or enter manually'));

  function refreshPicker(){
    candidates.splice(0,candidates.length,...(result.candidates||[]).filter(c=>(rule.rule_id?c.rule_id===rule.rule_id:c.property===rule.property)));
    picker.replaceChildren(option('','Choose a candidate or enter manually'));
    candidates.forEach((c,i)=>picker.append(option(i,`${c.value} ${c.unit} · page ${c.source_page} · ${c.method}`)));
  }
  fieldset.addEventListener('model-candidates',refreshPicker);refreshPicker();candidateLabel.append(picker);fieldset.append(candidateLabel);

  const snippet=document.createElement('small');fieldset.append(snippet);

  function field(key,title){const label=document.createElement('label');label.textContent=title;const input=document.createElement('input');input.dataset.field=key;input.setAttribute('aria-label',rule.property+' '+title);label.append(input);fieldset.append(label);}

  field('value','Measured value');field('unit','Reported unit');field('condition','Reported material condition');field('heat','Verified heat / lot identifier');

  const sourceLabel=document.createElement('label');sourceLabel.textContent='Evidence page';const source=document.createElement('select');source.dataset.field='source_page';source.setAttribute('aria-label',rule.property+' Evidence page');source.append(option('','Choose source page'));

  result.pages.forEach(p=>source.append(option(p.id,p.file+' · page '+p.number)));source.onchange=()=>{if(source.value)show(source.value);};sourceLabel.append(source);fieldset.append(sourceLabel);

  const label=document.createElement('label');const verified=document.createElement('input');verified.type='checkbox';verified.dataset.field='verified';label.append(verified,document.createTextNode('I checked the measured row, value, unit, material condition and heat linkage against the source documents.'));fieldset.append(label);

  const remove=document.createElement('button');remove.textContent='Remove this observation';remove.onclick=()=>{fieldset.remove();$('material-results').textContent='Observations changed. Check again.';};fieldset.append(remove);

  function populate(observation){fieldset.querySelectorAll('[data-field]').forEach(input=>{if(input.type==='checkbox')input.checked=observation.verified===true;else input.value=observation[input.dataset.field]||'';});}

  picker.onchange=()=>{const candidate=candidates[Number(picker.value)];if(picker.value===''||!candidate)return;populate(candidate);verified.checked=false;snippet.textContent=candidate.confidence+' · '+candidate.snippet;show(candidate.source_page,candidate.box);$('material-results').textContent='Candidate selected. Verify it before acceptance.';};

  fieldset.addEventListener('input',event=>{if(event.target!==verified)verified.checked=false;$('material-results').textContent='Observations changed. Check again.';});

  if(previous)populate(previous);else if(candidates.length===1){populate(candidates[0]);snippet.textContent='Unverified OCR candidate · '+candidates[0].snippet;}

  const add=group.querySelector('button');if(add&&add.parentNode===group)group.insertBefore(fieldset,add);else group.append(fieldset);

}

function observations(){if(!result)return [];return [...$('material-observations').querySelectorAll('fieldset')].map(fieldset=>{const observation={property:fieldset.dataset.property,rule_id:fieldset.dataset.rule};fieldset.querySelectorAll('[data-field]').forEach(input=>observation[input.dataset.field]=input.type==='checkbox'?input.checked:input.value);return observation;});}

$('check-material').onclick=async()=>{try{if(!result)throw Error('Complete inspection first');const checked=await api('/properties',{job,observations:observations()});$('material-results').textContent=checked.results.map(r=>`${r.property||'Material'} / ${r.heat||'unlinked'}: ${r.status}\n${r.reason}`).join('\n\n');}catch(error){$('material-results').textContent=error.message;}};



$('model-propose').onclick=async()=>{

  const button=$('model-propose');

  try {

    if(!result)throw Error('Open a completed case first');

    button.disabled=true;$('model-status').textContent='Reading selected OCR page with the local model...';

    const id=job;

    const audit=await api('/local-model/propose',{job:id,page:$('pages').value});

    if(job!==id)return;

    const key=c=>JSON.stringify([c.rule_id,c.source_page,c.value,c.unit,c.snippet]);
    const seen=new Set((result.candidates||[]).map(key));
    let added=0;
    for(const candidate of audit.candidates){if(!seen.has(key(candidate))){result.candidates.push(candidate);seen.add(key(candidate));added++;}}

    // Preserve every current observation and resolution; new proposals enter the picker only.

    const current=observations();

    const retained=savedReview;

    savedReview={...(retained||{}),observations:current};materialControls();savedReview=retained;

    $('model-status').textContent=`${added} new unverified proposals. Rejected proposals: ${audit.calls.reduce((n,c)=>n+(c.rejected||0),0)}. `+audit.calls.filter(c=>c.error).map(c=>c.error).join(' ')+(audit.truncated?' Row/time budget reached; remaining rows require manual review.':'');

  }catch(error){$('model-status').textContent=error.message;}finally{button.disabled=false;}

};

