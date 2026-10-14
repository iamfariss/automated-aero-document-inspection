"""Deterministic property comparison; callers must verify OCR and heat linkage first."""
from decimal import Decimal, InvalidOperation

def compare_properties(specification, observations):
    results = []
    if not specification or specification.get('status') != 'Approved':
        return [{'status': 'Needs review', 'reason': 'Approved specification required'}]
    rules = specification.get('rules', [])
    if not rules:
        return [{'status': 'Needs review', 'reason': 'No approved numerical rules'}]
    for rule in rules:
        matching = [o for o in observations if o.get('property') == rule['property'] and o.get('condition') == rule['condition']]
        result = {'property': rule['property'], 'clause': rule['clause'], 'status': 'Needs review'}
        if len(matching) != 1:
            result['reason'] = 'Missing or ambiguous property / material condition'
        else:
            observation = matching[0]
            result['observation'] = observation
            if not observation.get('source_page') or not observation.get('heat') or observation.get('verified') is not True:
                result['reason'] = 'Inspector-verified value, source page and heat linkage required'
            elif observation.get('unit') != rule['unit']:
                result['reason'] = 'Unit mismatch; no implicit conversion'
            else:
                try:
                    value = Decimal(str(observation['value']))
                    if not value.is_finite():
                        raise InvalidOperation
                    outside = rule.get('min') is not None and value < Decimal(str(rule['min'])) or (rule.get('max') is not None and value > Decimal(str(rule['max'])))
                    result.update(status='Outside approved limits' if outside else 'Within approved limits', reason='Inclusive limits compared; inspector retains final acceptance authority')
                except (KeyError, InvalidOperation, ValueError):
                    result['reason'] = 'Invalid numerical value'
        results.append(result)
    return results
