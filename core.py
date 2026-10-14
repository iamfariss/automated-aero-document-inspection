import json, re, hashlib, subprocess, sys, threading, queue, shutil, csv
from pathlib import Path
from datetime import datetime
import pypdfium2 as pdfium
from PIL import Image
ROOT = Path(__file__).resolve().parent

def ocr(image):
    p = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'ocr.ps1'), '-ImagePath', str(image.resolve())], capture_output=True, encoding='utf-8', errors='replace', creationflags=134217728)
    if p.returncode:
        raise RuntimeError(p.stderr.strip())
    return json.loads(p.stdout)

def classify(text):
    t = text.upper()
    if 'GOODS' in t and 'RECEIPT' in t and ('SLIP' in t):
        return 'GR'
    if 'CERTIF' in t and ('CONFORMANCE' in t or 'CONFORMITY' in t):
        return 'COC'
    if 'SHIPPER' in t or 'DELIVERY ORDER' in t or 'PACKING LIST' in t:
        return 'Shipping'
    if any((x in t for x in ['COMPOSITION', 'TENSILE', 'HARDNESS', 'MECHANICAL'])):
        return 'Test report'
    return 'Other / review'

def region(page, x1, y1, x2, y2):
    w, h = page['size']
    words = [v for line in page['ocr']['lines'] for v in line['words'] if x1 * w <= v['x'] < x2 * w and y1 * h <= v['y'] < y2 * h]
    words.sort(key=lambda v: (round(v['y'] / 10), v['x']))
    return ' '.join((v['text'] for v in words))

def gr_fields(p):
    boxes = {'PO': (0.15, 0.23, 0.33, 0.26), 'Part': (0.15, 0.335, 0.4, 0.354), 'Batch': (0.15, 0.371, 0.4, 0.39), 'Delivery': (0.69, 0.187, 0.93, 0.207), 'Revision': (0.68, 0.439, 0.78, 0.456), 'Quantity': (0.15, 0.423, 0.28, 0.439)}
    return {k: region(p, *b) for k, b in boxes.items()}

def normalized(s):
    return re.sub('[^A-Z0-9]', '', s.upper())

def inspect(pages):
    findings = []
    grs = [p for p in pages if p['kind'] == 'GR']
    others = [p for p in pages if p['kind'] != 'GR']
    if not grs:
        findings.append(('Needs review', 'No GR slip recognized', 'Check document classification', None))
    for p in pages:
        if p['kind'] == 'Other / review':
            findings.append(('Needs review', f"Page {p['number']} unclassified", 'Review page type and readability', p['id']))
        if p.get('duplicate'):
            findings.append(('Needs review', 'Exact duplicate page', f"Duplicate of {p['duplicate']}; excluded from evidence matching", p['id']))
    for g in grs:
        f = gr_fields(g)
        g['fields'] = f
        findings.append(('Needs review', f"GR {g['number']}: confirm OCR fields", json.dumps(f, ensure_ascii=False), g['id']))
        if not any((p['kind'] == 'COC' for p in others)):
            findings.append(('Needs review', 'No separate COC recognized', 'A shipper may contain a certification statement; inspector must determine applicability.', g['id']))
        if not any((p['kind'] == 'Shipping' for p in others)):
            findings.append(('Needs review', 'No shipping document recognized', 'Check missing documents or classification.', g['id']))
        for key in ['Part', 'PO', 'Delivery']:
            value = f.get(key, '')
            n = normalized(value)
            if len(n) < 4:
                findings.append(('Needs review', f'{key} unreadable', value or 'No candidate extracted', g['id']))
                continue
            targets = [p for p in others if not p.get('duplicate') and (key != 'Delivery' or p['kind'] == 'Shipping')]
            hits = [p['id'] for p in targets if n in normalized(p['ocr']['text'])]
            findings.append(('Candidate match' if hits else 'Needs review', f'{key}: {value}', 'Text found on ' + ', '.join(hits) + '; confirm correct line item.' if hits else 'No exact normalized text match in supporting pages.', g['id']))
        findings.append(('Needs review', 'Quantity, unit and revision reconciliation', 'Multiple shipment lines and duplicate documents require line-item review; totals are not automatically summed.', g['id']))
        findings.append(('Needs review', 'Material compliance pending', 'Approved specification, revision, material condition, heat linkage and units must be established. Chemistry and mechanical tables are OCR evidence only.', g['id']))
    return findings
