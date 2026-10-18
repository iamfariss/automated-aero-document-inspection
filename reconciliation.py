"""Delivery line candidates and conservative quantity reconciliation."""
import re
from decimal import Decimal

def quantity(value):
    hit = re.fullmatch('\\s*(\\d+(?:\\.\\d+)?)\\s+(EA|PCS|PC|MM|KG|M)\\s*', value, re.I)
    return (Decimal(hit[1]), hit[2].upper()) if hit else None

def reconcile(pages, shipping):
    result = []
    for page in pages:
        if page.get('kind') != 'GR' or page.get('duplicate'):
            continue
        fields = page.get('fields', {})
        part = fields.get('Part', '').strip()
        received = quantity(fields.get('Quantity', ''))
        matching = [r for r in shipping if r['part'] == part]
        unique = {(r['part'], r['quantity'], r['unit'], r['source_page']): r for r in matching}
        row = {'source_page': page['id'], 'part': part, 'received': fields.get('Quantity', ''), 'shipping': list(unique.values()), 'status': 'Needs review'}
        if received and len(unique) == 1:
            shipped = next(iter(unique.values()))
            if received == (Decimal(shipped['quantity']), shipped['unit']):
                row.update(status='Candidate match', reason='One explicit shipping line agrees; verify line scope and document identity')
            else:
                row.update(status='Potential discrepancy', reason='Received and shipping quantity or unit differ')
        else:
            row['reason'] = 'Missing or multiple shipping line candidates; quantities are not summed across ambiguous copies'
        result.append(row)
    return result
