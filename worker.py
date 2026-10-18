"""Isolated PDF and Windows OCR worker; started by cases.py."""
import json, sys, hashlib
from pathlib import Path
import pypdfium2 as pdfium
from core import enhanced_ocr, classify, inspect
from extraction import extract_candidates, shipping_rows
from reconciliation import reconcile

def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)

def run(case):
    request = json.loads((case / 'request.json').read_text(encoding='utf-8'))
    pages = []
    seen = {}
    for document in request['documents']:
        path = case / document['stored']
        if hashlib.sha256(path.read_bytes()).hexdigest() != document['sha256']:
            raise ValueError('Source checksum mismatch')
        with pdfium.PdfDocument(str(path)) as pdf:
            if not 1 <= len(pdf) <= 100 or len(pages) + len(pdf) > 100:
                raise ValueError('Batch must contain 1 to 100 total PDF pages')
            for index in range(len(pdf)):
                write_json(case / 'progress.json', {'progress': f"{document['name']}: page {index + 1}/{len(pdf)}"})
                page = pdf[index]
                width, height = page.get_size()
                if min(width, height) <= 0:
                    raise ValueError('Invalid page dimensions')
                scale = min(3, 2400 / max(width, height))
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert('RGB')
                digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
                pid = f"{document['index']}:{index + 1}"
                name = f"{document['index']}_{index + 1}.png"
                image.save(case / name)
                data = enhanced_ocr(case / name)
                pages.append({'id': pid, 'file': document['name'], 'number': index + 1, 'image': name, 'size': image.size, 'ocr': data, 'kind': classify(data['text']), 'duplicate': seen.get(digest)})
                seen.setdefault(digest, pid)
                image.close()
                bitmap.close()
                page.close()
    findings = inspect(pages)
    spec = request.get('specification')
    findings.append(('Needs review', 'Governing specifications', spec['code'] + ' revision ' + spec['revision'] + '; confirm applicability for each item.' if spec else 'No approved specifications selected.', None))
    shipping = shipping_rows(pages)
    reconciled = reconcile(pages, shipping)
    for line in reconciled:
        findings.append((line['status'], 'Quantity reconciliation: ' + (line['part'] or 'unreadable part'), line['reason'], line['source_page']))
    result = {'reconciliation': reconciled, 'pages': pages, 'findings': findings, 'specification': spec, 'documents': request['documents'], 'candidates': extract_candidates(pages, spec), 'shipping_candidates': shipping}
    write_json(case / 'analysis.json', result)
if __name__ == '__main__':
    try:
        run(Path(sys.argv[1]))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
