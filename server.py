from core import ocr, classify, gr_fields, inspect, ROOT
import json, base64, threading, uuid, hashlib, csv, webbrowser, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import pypdfium2 as pdfium
from registry import Registry
import secrets
REGISTRY = Registry(ROOT / 'data')
SESSIONS = {}
JOBS = {}

def process(job, files, specification=None):
    try:
        case = ROOT / 'cases' / job
        case.mkdir(parents=True)
        pages = []
        seen = {}
        for n, f in enumerate(files, 1):
            name = Path(f['name']).name
            if not name.lower().endswith('.pdf'):
                raise ValueError('Only PDF files accepted')
            path = case / f'{n}_{name}'
            path.write_bytes(base64.b64decode(f['data'], validate=True))
            doc = pdfium.PdfDocument(str(path))
            for i in range(len(doc)):
                JOBS[job]['progress'] = f'{name}: page {i + 1}/{len(doc)}'
                im = doc[i].render(scale=2).to_pil().convert('RGB')
                im.thumbnail((2400, 2400))
                img = case / f'{n}_{i + 1}.png'
                im.save(img)
                digest = hashlib.sha256(im.tobytes()).hexdigest()
                pid = f'{n}:{i + 1}'
                data = ocr(img)
                pages.append({'id': pid, 'file': name, 'number': i + 1, 'image': img.name, 'size': im.size, 'ocr': data, 'kind': classify(data['text']), 'duplicate': seen.get(digest)})
                seen.setdefault(digest, pid)
            doc.close()
        findings = inspect(pages)
        findings.append(('Needs review', 'Governing specification', 'Selected ' + specification['code'] + ' revision ' + specification['revision'] + '; confirm applicability. Numerical property checks remain pending.' if specification else 'No approved specification selected.', None))
        result = {'pages': pages, 'findings': findings, 'specification': specification}
        (case / 'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        JOBS[job].update(state='done', result=result)
    except Exception as e:
        JOBS[job].update(state='error', error=str(e))

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def reply(self, data, status=200, mime='application/json'):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8765', 'localhost:8765'):
            return self.reply({'error': 'Invalid host'}, 403)
        if self.path == '/registry':
            return self.reply({'configured': REGISTRY.configured(), 'specs': REGISTRY.list()})
        if self.path == '/registry/audit':
            try:
                self.admin()
                return self.reply(REGISTRY.history())
            except ValueError as e:
                return self.reply({'error': str(e)}, 403)
        if self.path.startswith('/specification/'):
            try:
                return self.reply(REGISTRY.pdf(int(self.path.rsplit('/', 1)[1])), mime='application/pdf')
            except Exception as e:
                return self.reply({'error': str(e)}, 404)
        if self.path == '/governance.html':
            return self.reply((ROOT / 'governance.html').read_bytes(), mime='text/html; charset=utf-8')
        if self.path == '/':
            return self.reply((ROOT / 'ui.html').read_bytes(), mime='text/html; charset=utf-8')
        parts = self.path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'job':
            return self.reply(JOBS.get(parts[1], {'state': 'error', 'error': 'Unknown job'}))
        if len(parts) == 3 and parts[0] == 'image' and (parts[1] in JOBS) and (parts[2] in [p['image'] for p in JOBS[parts[1]].get('result', {}).get('pages', [])]):
            return self.reply((ROOT / 'cases' / parts[1] / parts[2]).read_bytes(), mime='image/png')
        self.reply({'error': 'Not found'}, 404)

    def admin(self):
        token = self.headers.get('Authorization', '').removeprefix('Bearer ')
        session = SESSIONS.get(token)
        if not session or session['expires'] < time.time():
            raise ValueError('Admin login required')
        return session['name']

    def do_POST(self):
        try:
            if self.headers.get('Host') not in ('127.0.0.1:8765', 'localhost:8765'):
                return self.reply({'error': 'Invalid host'}, 403)
            if self.headers.get('Origin') != 'http://127.0.0.1:8765':
                return self.reply({'error': 'Invalid origin'}, 403)
            length = int(self.headers.get('Content-Length', 0))
            if length > 100000000:
                raise ValueError('Batch exceeds 100 MB upload limit')
            data = json.loads(self.rfile.read(length))
            if self.path == '/admin/setup':
                REGISTRY.setup(data['name'], data['password'])
                return self.reply({'configured': True})
            if self.path == '/admin/login':
                actor = REGISTRY.login(data['password'])
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = {'name': actor, 'expires': time.time() + 1800}
                return self.reply({'token': token, 'name': actor})
            if self.path == '/admin/logout':
                SESSIONS.pop(self.headers.get('Authorization', '').removeprefix('Bearer '), None)
                return self.reply({'logged_out': True})
            if self.path == '/specification/upload':
                raw = base64.b64decode(data['data'], validate=True)
                if len(raw) > 30000000:
                    raise ValueError('Specification exceeds 30 MB')
                document = pdfium.PdfDocument(raw)
                if not len(document):
                    raise ValueError('Empty PDF')
                document.close()
                sid = REGISTRY.upload(data, raw)
                return self.reply({'id': sid, 'status': 'Draft'})
            if self.path == '/specification/transition':
                actor = self.admin()
                REGISTRY.transition(int(data['id']), data['action'], actor, data['reason'])
                return self.reply({'updated': True})
            if self.path == '/inspect':
                if not data.get('files'):
                    raise ValueError('Select PDFs')
                specification = REGISTRY.snapshot(int(data['specification_id'])) if data.get('specification_id') else None
                job = uuid.uuid4().hex
                JOBS[job] = {'state': 'running', 'progress': 'Starting OCR'}
                threading.Thread(target=process, args=(job, data['files'], specification), daemon=True).start()
                return self.reply({'job': job})
            if self.path == '/review':
                job = data['job']
                if job not in JOBS or JOBS[job]['state'] != 'done':
                    raise ValueError('Inspection incomplete')
                if not data.get('inspector', '').strip() or not data.get('notes', '').strip():
                    raise ValueError('Inspector and review notes required')
                if data['decision'] not in ['Needs review', 'Accepted by inspector', 'Rejected by inspector']:
                    raise ValueError('Invalid decision')
                case = ROOT / 'cases' / job
                data['timestamp'] = datetime.now().isoformat()
                data['specification'] = JOBS[job]['result'].get('specification')
                with (case / 'review-history.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps(data) + '\n')
                with (case / 'findings.csv').open('w', newline='', encoding='utf-8-sig') as f:
                    w = csv.writer(f)
                    w.writerow(['Status', 'Check', 'Evidence / action', 'Page'])
                    w.writerows(JOBS[job]['result']['findings'])
                return self.reply({'saved': str(case)})
            self.reply({'error': 'Not found'}, 404)
        except Exception as e:
            self.reply({'error': str(e)}, 400)
if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Local inspection: http://127.0.0.1:8765 — leave this window open.')
    threading.Timer(1, lambda: webbrowser.open('http://127.0.0.1:8765')).start()
    server.serve_forever()
