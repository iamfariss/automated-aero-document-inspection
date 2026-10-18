/* Material observations are recomputed on the server when the review is saved. */
function materialControls() {
  const host = $('material-observations');
  host.replaceChildren();
  $('material-results').textContent = '';
  const spec = result.specification;
  $('material-spec').textContent = spec ? `${spec.code} revision ${spec.revision} — approval: ${spec.approved_by}` : 'No approved specification selected for this inspection.';
  const rules = spec?.rules || [];
  if (!rules.length) {
    host.textContent = 'No approved numerical requirements are available. Material checks remain Needs review.';
    return;
  }
  rules.forEach((rule, index) => {
    const fieldset = document.createElement('fieldset');
    fieldset.dataset.property = rule.property;
    const legend = document.createElement('legend');
    legend.textContent = `${rule.property} · ${rule.clause}`;
    fieldset.append(legend);
    const requirement = document.createElement('p');
    requirement.textContent = `Approved condition: ${rule.condition}. Limits: ${rule.min ?? 'no minimum'} to ${rule.max ?? 'no maximum'} ${rule.unit} (inclusive).`;
    fieldset.append(requirement);
    function field(key, title, value = '') {
      const label = document.createElement('label');
      label.textContent = title + ' ';
      const input = document.createElement('input');
      input.dataset.field = key;
      input.value = value;
      input.setAttribute('aria-label', `${rule.property} ${title} ${index + 1}`);
      input.style.width = '90%';
      label.append(input);
      fieldset.append(label, document.createElement('br'));
    }
    field('value', 'Measured value');
    field('unit', 'Reported unit');
    field('condition', 'Reported material condition');
    field('heat', 'Verified heat / lot identifier');
    const sourceLabel = document.createElement('label');
    sourceLabel.textContent = 'Evidence page ';
    const source = document.createElement('select');
    source.dataset.field = 'source_page';
    source.setAttribute('aria-label', `${rule.property} Evidence page ${index + 1}`);
    const blank = document.createElement('option');
    blank.value = ''; blank.textContent = 'Choose source page'; source.append(blank);
    result.pages.forEach(page => {
      const option = document.createElement('option');
      option.value = page.id;
      option.textContent = `${page.file} · page ${page.number}`;
      source.append(option);
    });
    source.onchange = () => { if (source.value) show(source.value); };
    sourceLabel.append(source); fieldset.append(sourceLabel);
    const label = document.createElement('label');
    const verified = document.createElement('input');
    verified.type = 'checkbox'; verified.dataset.field = 'verified';
    label.append(verified, document.createTextNode(' I checked this value, unit, material condition and heat linkage against the source documents.'));
    fieldset.append(document.createElement('p'), label);
    fieldset.addEventListener('input', event => {
      if (event.target !== verified) verified.checked = false;
      $('material-results').textContent = 'Values changed. Run the material check again.';
    });
    host.append(fieldset);
  });
}
function observations() {
  if (!result) return [];
  return [...$('material-observations').querySelectorAll('fieldset')].map(fieldset => {
    const observation = { property: fieldset.dataset.property };
    fieldset.querySelectorAll('[data-field]').forEach(input => {
      observation[input.dataset.field] = input.type === 'checkbox' ? input.checked : input.value;
    });
    return observation;
  });
}
$('check-material').onclick = async () => {
  try {
    if (!result) throw Error('Complete inspection first');
    const checked = await api('/properties', {job, observations: observations()});
    $('material-results').textContent = checked.results.map(r => `${r.property || 'Material checks'}: ${r.status}\n${r.reason}`).join('\n\n');
  } catch (error) { $('material-results').textContent = error.message; }
};
