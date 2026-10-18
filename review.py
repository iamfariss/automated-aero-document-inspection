"""Validate review observations against the inspection's frozen specification."""
from properties import compare_properties

def evaluate_observations(analysis, observations):
    if not isinstance(observations, list) or len(observations) > 500:
        raise ValueError('Provide at most 500 material observations')
    page_ids = {page['id'] for page in analysis['pages']}
    cleaned = []
    allowed = ('property', 'condition', 'unit', 'value', 'source_page', 'heat')
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
    results = compare_properties(analysis.get('specification'), cleaned)
    return {'observations': cleaned, 'results': results}


def prepare_review(analysis, request, timestamp):
    inspector = request.get('inspector', '')
    notes = request.get('notes', '')
    if not isinstance(inspector, str) or not isinstance(notes, str) or not inspector.strip() or not notes.strip():
        raise ValueError('Inspector and review notes required')
    decision = request.get('decision')
    if decision not in ('Needs review', 'Accepted by inspector', 'Rejected by inspector'):
        raise ValueError('Invalid decision')
    checked = evaluate_observations(analysis, request.get('observations', []))
    if decision == 'Accepted by inspector' and any(r['status'] != 'Within approved limits' for r in checked['results']):
        raise ValueError('Material checks are unresolved or outside approved limits; keep Needs review or reject')
    return {'timestamp': timestamp, 'inspector': inspector.strip(), 'notes': notes.strip(),
            'decision': decision, 'specification': analysis.get('specification'),
            'observations': checked['observations'], 'property_results': checked['results']}
