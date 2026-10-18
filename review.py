"""Validate review observations against the inspection's frozen specification."""
from properties import compare_properties

def evaluate_observations(analysis, observations):
    if not isinstance(observations, list) or len(observations) > 500:
        raise ValueError('Provide at most 500 material observations')
    page_ids = {page['id'] for page in analysis['pages']}
    cleaned = []
    allowed = ('property', 'condition', 'unit', 'value', 'source_page', 'heat', 'rule_id')
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError('Each observation must be an object')
        observation = {}
        for key in allowed:
            value = item.get(key, '')
            if not isinstance(value, str) or len(value) > 1000:
                raise ValueError('Observation fields must be text of at most 1000 characters')
            observation[key] = value.strip()
        if observation['source_page'] and observation['source_page'] not in page_ids:
            raise ValueError('Observation source page does not belong to this inspection')
        observation['verified'] = item.get('verified') is True
        cleaned.append(observation)
    rules = (analysis.get('specification') or {}).get('rules', [])
    known = {(rule['property'], rule.get('rule_id', '')) for rule in rules}
    if any(((o['property'], o.get('rule_id', '')) not in known for o in cleaned)) and rules:
        raise ValueError('Observation does not identify an approved requirement in this case')
    results = compare_properties(analysis.get('specification'), cleaned)
    return {'observations': cleaned, 'results': results}

def prepare_review(analysis, request, timestamp):
    inspector = request.get('inspector', '')
    notes = request.get('notes', '')
    if not isinstance(inspector, str) or not isinstance(notes, str) or (not inspector.strip()) or (not notes.strip()) or (len(inspector) > 200) or (len(notes) > 20000):
        raise ValueError('Inspector and review notes required')
    decision = request.get('decision')
    if decision not in ('Needs review', 'Accepted by inspector', 'Rejected by inspector'):
        raise ValueError('Invalid decision')
    checked = evaluate_observations(analysis, request.get('observations', []))
    if decision == 'Accepted by inspector' and any((r['status'] not in ('Within approved limits', 'Not required by approved specification') for r in checked['results'])):
        raise ValueError('Material checks are unresolved or outside approved limits; keep Needs review or reject')
    resolutions = request.get('resolutions', [])
    if not isinstance(resolutions, list) or len(resolutions) > 1000:
        raise ValueError('Document review resolutions must be a list of at most 1000 entries')
    sanitized = []
    for r in resolutions:
        if not isinstance(r, dict) or not all((isinstance(r.get(k), str) for k in ('id', 'resolution', 'note'))) or len(r['note']) > 10000:
            raise ValueError('Invalid document finding resolution')
        sanitized.append({k: r[k].strip() for k in ('id', 'resolution', 'note')})
    resolutions = sanitized
    if decision == 'Accepted by inspector' and analysis.get('findings'):
        by_id = {r.get('id'): r for r in resolutions if isinstance(r, dict)}
        for index in range(len(analysis['findings'])):
            resolution = by_id.get(str(index), {})
            if resolution.get('resolution') not in ('Confirmed', 'Not applicable') or not isinstance(resolution.get('note'), str) or (not resolution['note'].strip()):
                raise ValueError('Resolve every document finding with a note before acceptance')
    return {'resolutions': resolutions, 'timestamp': timestamp, 'inspector': inspector.strip(), 'notes': notes.strip(), 'decision': decision, 'specification': analysis.get('specification'), 'observations': checked['observations'], 'property_results': checked['results']}
