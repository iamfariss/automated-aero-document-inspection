"""Conservative OCR extraction. Every candidate requires inspector verification."""
import re
from statistics import median
NUMBER = re.compile('(?<![A-Za-z0-9])[-+]?\\d+(?:\\.\\d+)?(?:[eE][-+]?\\d+)?(?![A-Za-z0-9])')
IGNORE = re.compile('\\b(min(?:imum)?|max(?:imum)?|spec(?:ification)?|requirement|limit)\\b', re.I)

def rows(page):
    words = [dict(w) for line in page.get('ocr', {}).get('lines', []) for w in line.get('words', [])]
    words.sort(key=lambda w: (w['y'] + w['height'] / 2, w['x']))
    groups = []
    for word in words:
        center = word['y'] + word['height'] / 2
        tolerance = max(3, word['height'] * 0.45)
        if groups and abs(center - median((w['y'] + w['height'] / 2 for w in groups[-1]))) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [sorted(group, key=lambda w: w['x']) for group in groups]

def text(row):
    return ' '.join((w['text'] for w in row))

def evidence_box(words):
    left = min((w['x'] for w in words))
    top = min((w['y'] for w in words))
    return [left, top, max((w['x'] + w['width'] for w in words)) - left, max((w['y'] + w['height'] for w in words)) - top]

def matches(label, content):
    return re.search('(?<!\\w)' + re.escape(label) + '(?!\\w)', content, re.I)

def trace_candidates(page):
    content = '\n'.join((text(r) for r in rows(page))) or page.get('ocr', {}).get('text', '')
    heats = sorted(set(re.findall('\\b(?:heat|melt|lot|batch)\\s*(?:no\\.?|number|#)?\\s*[:#]?\\s+([A-Z0-9][A-Z0-9/-]{2,})', content, re.I)))
    condition = re.findall('\\b(?:condition|temper)\\s*[:=]\\s*([A-Z0-9/-]+)', content, re.I)
    return (heats, list(dict.fromkeys(condition)))

def extract_candidates(pages, specification):
    candidates = []
    for page in pages:
        if page.get('duplicate') or page.get('kind') not in ('COC', 'Test report'):
            continue
        table = rows(page)
        heats, conditions = trace_candidates(page)
        for index, rule in enumerate((specification or {}).get('rules', [])):
            labels = [rule['property']] + rule.get('aliases', [])
            rule_id = rule.get('rule_id', str(index))
            for row_index, row in enumerate(table):
                content = text(row)
                label = next((label for label in labels if matches(label, content)), None)
                if not label or IGNORE.search(content):
                    continue
                match = matches(label, content)
                tail = content[match.end():]
                direct = list(NUMBER.finditer(tail))
                if len(direct) == 1 and (':' in tail[:direct[0].start() + 1] or matches(rule['unit'], tail)):
                    unit = rule['unit'] if matches(rule['unit'], tail) else ''
                    candidates.append(candidate(page, rule, rule_id, (tail[direct[0].start() - 1] if direct[0].start() > 0 and tail[direct[0].start() - 1] in '<>' else '') + direct[0].group(), unit, heats, conditions, row, content, 'labelled value'))
                    continue
                header_words = [w for w in row if matches(label, w['text'])]
                if not header_words:
                    continue
                header = header_words[0]
                center = header['x'] + header['width'] / 2
                other_centers = sorted((w['x'] + w['width'] / 2 for w in row if w is not header))
                left = max((x for x in other_centers if x < center), default=center - 100)
                right = min((x for x in other_centers if x > center), default=center + 100)
                centers = sorted((w['x'] + w['width'] / 2 for w in row))
                gaps = [b - a for a, b in zip(centers, centers[1:]) if b - a > 10]
                radius = min((right - left) / 4, median(gaps) * 0.42 if gaps else 35)
                following = table[row_index + 1:row_index + 22]
                anchors = [i for i, r in enumerate(following) if re.search('\\b(actual|measured|results?|samples?)\\b', text(r), re.I)]
                for offset, below in enumerate(following):
                    below_text = text(below)
                    if not anchors or not any((anchor - 2 <= offset <= anchor + 6 for anchor in anchors)):
                        continue
                    if sum((bool(NUMBER.fullmatch(w['text'])) for w in below)) < 3:
                        continue
                    if IGNORE.search(below_text):
                        continue
                    values = [w for w in below if abs(w['x'] + w['width'] / 2 - center) <= radius and NUMBER.fullmatch(w['text']) and (not re.fullmatch('0\\d+', w['text']))]
                    if len(values) != 1:
                        continue
                    value = values[0]
                    unit = rule['unit'] if matches(rule['unit'], content + ' ' + below_text) else ''
                    candidates.append(candidate(page, rule, rule_id, value['text'], unit, heats, conditions, [header, value], below_text, 'table column — verify measured row'))
    unique = {}
    for c in candidates:
        key = (c['rule_id'], c['source_page'], c['value'], tuple(c['box']))
        unique[key] = c
    return list(unique.values())[:500]

def candidate(page, rule, rule_id, value, unit, heats, conditions, words, snippet, method):
    return {'rule_id': rule_id, 'property': rule['property'], 'value': value, 'unit': unit, 'condition': conditions[0] if len(conditions) == 1 else '', 'heat': heats[0] if len(heats) == 1 else '', 'heat_candidates': heats, 'source_page': page['id'], 'box': evidence_box(words), 'snippet': snippet, 'method': method, 'verified': False, 'confidence': 'Unverified OCR candidate'}

def shipping_rows(pages):
    """Extract part/quantity candidates only from rows with an explicit unit."""
    result = []
    pattern = re.compile('\\b(\\d{5,}(?:-\\d+)*)\\b.*?\\b(\\d+(?:\\.\\d+)?)\\s+(EA|PCS|PC|MM|KG|M)\\b', re.I)
    for page in pages:
        if page.get('kind') != 'Shipping' or page.get('duplicate'):
            continue
        for row in rows(page):
            content = text(row)
            for hit in pattern.finditer(content):
                result.append({'part': hit[1], 'quantity': hit[2], 'unit': hit[3].upper(), 'source_page': page['id'], 'snippet': content, 'box': evidence_box(row)})
    return result
