"""Frozen selection of one or more administrator-approved specifications."""
import copy

def combine_specifications(snapshots):
    if not snapshots:
        return None
    rules = []
    for spec in snapshots:
        for index, rule in enumerate(spec['rules']):
            rules.append(copy.deepcopy(rule) | {'rule_id': f"{spec['id']}:{index}", 'specification_id': spec['id'], 'specification_code': spec['code'], 'specification_revision': spec['revision']})
    return {'status': 'Approved', 'code': ' + '.join((s['code'] for s in snapshots)), 'revision': ' / '.join((s['revision'] for s in snapshots)), 'approved_by': ', '.join(dict.fromkeys((s['approved_by'] for s in snapshots))), 'material_required': any((s.get('material_required', True) for s in snapshots)), 'rules': rules, 'sources': copy.deepcopy(snapshots)}
