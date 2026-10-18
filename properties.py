"""Deterministic comparison of approved requirements to verified heat-level evidence."""
from decimal import Decimal, InvalidOperation

def compare_properties(specification, observations):
    if not specification or specification.get('status') != 'Approved':
        return [{'status': 'Needs review', 'reason': 'Approved specification required'}]
    rules = specification.get('rules', [])
    if not rules and specification.get('material_required') is False:
        return [{'status': 'Not required by approved specification', 'reason': 'Admin-approved document-only scope; resolve every document finding'}]
    if not rules:
        return [{'status': 'Needs review', 'reason': 'No approved numerical rules'}]
    results = []
    for rule in rules:
        matching = [o for o in observations if o.get('property') == rule['property'] and o.get('condition') == rule['condition'] and (not rule.get('rule_id') or o.get('rule_id') == rule['rule_id'])]
        groups = {}
        for observation in matching:
            groups.setdefault(observation.get('heat', ''), []).append(observation)
        if not groups:
            groups[''] = []
        for heat, group in groups.items():
            result = {'property': rule['property'], 'clause': rule['clause'], 'rule_id': rule.get('rule_id', ''), 'specification_code': rule.get('specification_code', specification.get('code', '')), 'specification_revision': rule.get('specification_revision', specification.get('revision', '')), 'heat': heat, 'status': 'Needs review', 'limits': {'min': rule.get('min'), 'max': rule.get('max'), 'unit': rule['unit']}}
            if len(group) != 1:
                result['reason'] = 'Missing or ambiguous property / material condition / heat'
            else:
                observation = group[0]
                result['observation'] = observation
                if not observation.get('source_page') or not heat or observation.get('verified') is not True:
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
