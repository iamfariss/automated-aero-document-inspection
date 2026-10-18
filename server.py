"""Offline loopback application: registry, persistent cases, reviews and scan inbox."""
import base64, csv, html, io, json, secrets, threading, time, webbrowser, zipfile, subprocess, sys, tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import ROOT
from registry import Registry
from selection import combine_specifications
from review import evaluate_observations, prepare_review
from cases import CaseStore, Inbox
REGISTRY = Registry(ROOT / 'data')
STORE = CaseStore(ROOT / 'cases')
SESSIONS = {}
ATTEMPTS = []
AUTH_LOCK = threading.RLock()

def selection(ids):
    if not isinstance(ids, list) or len(ids) > 8:
        raise ValueError('Select at most 8 approved specifications')
    if any((isinstance(i, bool) or not isinstance(i, (str, int)) for i in ids)):
        raise ValueError('Invalid specification selection')
    ids = list(dict.fromkeys((int(i) for i in ids)))
    return combine_specifications([REGISTRY.snapshot(i) for i in ids])

def create_case(files, specification, origin='Manual upload'):
    sources = {}
    for source in (specification or {}).get('sources', []):
        raw = REGISTRY.pdf(source['id'])
        import hashlib
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('Archived source differs from approved snapshot')
        sources[f"specification_{source['id']}.pdf"] = raw
    return STORE.submit(files, specification, origin, sources)

def csv_safe(row):
    return ["'" + str(value) if str(value).startswith(('=', '+', '-', '@', '\t', '\r')) else value for value in row]

def save_review(case, analysis, request):
    record = prepare_review(analysis, request, datetime.now(timezone.utc).isoformat())
    with STORE.lock:
        with (case / 'review-history.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')
        with (case / 'findings.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Status', 'Check', 'Evidence / action', 'Page'])
            writer.writerows((csv_safe(row) for row in analysis['findings']))
        with (case / 'material-checks.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Status', 'Specification', 'Revision', 'Property', 'Clause', 'Value', 'Unit', 'Condition', 'Heat', 'Source page', 'Reason'])
            for item in record['property_results']:
                o = item.get('observation', {})
                writer.writerow(csv_safe([item['status'], item.get('specification_code', ''), item.get('specification_revision', ''), item.get('property', ''), item.get('clause', '')] + [o.get(k, '') for k in ('value', 'unit', 'condition', 'heat', 'source_page')] + [item['reason']]))
        esc = lambda value: html.escape(str(value))
        report = '<!doctype html><meta charset="utf-8"><title>Inspection review</title><style>body{font:16px Segoe UI;margin:40px}pre{white-space:pre-wrap}img{max-width:100%}</style><h1>Inspection review</h1>'
        report += '<p>' + esc(record['decision']) + ' | ' + esc(record['inspector']) + ' | ' + esc(record['timestamp']) + '</p><pre>' + esc(json.dumps(record, indent=2)) + '</pre>'
        for page in analysis['pages']:
            report += '<h2>' + esc(page['file']) + ' page ' + str(page['number']) + '</h2><img src="' + esc(page['image']) + '">'
        (case / 'report.html').write_text(report, encoding='utf-8')
    return record

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def reply(self, data, status=200, mime='application/json', filename=None):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        self.wfile.write(payload)

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:8765', 'localhost:8765')

    def admin(self):
        token = self.headers.get('Authorization', '').removeprefix('Bearer ')
        with AUTH_LOCK:
            session = SESSIONS.get(token)
            if not session or session['expires'] < time.time():
                SESSIONS.pop(token, None)
                raise ValueError('Admin login required')
            return session['name']

    def do_GET(self):
        try:
            if not self.valid_host():
                return self.reply({'error': 'Invalid host'}, 403)
            static = {'/': 'ui.html', '/review.js': 'review.js', '/ui.js': 'ui.js', '/style.css': 'style.css', '/governance.html': 'governance.html', '/governance.js': 'governance.js'}
            if self.path in static:
                name = static[self.path]
                mime = 'application/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'text/html'
                return self.reply((ROOT / name).read_bytes(), mime=mime + '; charset=utf-8')
            if self.path == '/registry':
                return self.reply({'configured': REGISTRY.configured(), 'specs': REGISTRY.list()})
            if self.path == '/registry/audit':
                self.admin()
                return self.reply(REGISTRY.history())
            if self.path == '/scanner-profiles':
                return self.reply(REGISTRY.scanner_profiles())
            if self.path == '/cases':
                return self.reply(STORE.list())
            if self.path == '/inbox':
                files = []
                for path in (ROOT / 'inbox').glob('*/inspection-status.json'):
                    try:
                        files.append({'batch': path.parent.name} | json.loads(path.read_text(encoding='utf-8')))
                    except ValueError:
                        pass
                return self.reply({'path': str(ROOT / 'inbox'), 'batches': files})
            parts = self.path.strip('/').split('/')
            if len(parts) == 2 and parts[0] == 'specification':
                return self.reply(REGISTRY.pdf(int(parts[1])), mime='application/pdf')
            if len(parts) == 2 and parts[0] == 'job':
                return self.reply(STORE.get(parts[1]))
            if len(parts) == 3 and parts[0] == 'image':
                state = STORE.get(parts[1])
                images = {p['image'] for p in state.get('result', {}).get('pages', [])}
                if parts[2] not in images:
                    raise ValueError('Unknown page image')
                return self.reply((STORE.path(parts[1]) / parts[2]).read_bytes(), mime='image/png')
            if len(parts) == 3 and parts[0] == 'case' and (parts[2] == 'export'):
                case = STORE.path(parts[1])
                analysis = STORE.get(parts[1])
                if analysis['state'] != 'done':
                    raise ValueError('Case not complete')
                stream = io.BytesIO()
                with STORE.lock, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for path in case.iterdir():
                        if path.is_file() and path.suffix in ('.json', '.jsonl', '.csv', '.html', '.png', '.pdf'):
                            archive.write(path, path.name)
                return self.reply(stream.getvalue(), mime='application/zip', filename='inspection-' + parts[1] + '.zip')
            return self.reply({'error': 'Not found'}, 404)
        except (ValueError, KeyError, OSError) as error:
            return self.reply({'error': str(error)}, 400)

    def do_POST(self):
        try:
            if not self.valid_host():
                return self.reply({'error': 'Invalid host'}, 403)
            if self.headers.get('Origin') != 'http://127.0.0.1:8765':
                return self.reply({'error': 'Invalid origin'}, 403)
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 135000000:
                raise ValueError('Invalid request size; maximum 135 MB encoded')
            self.connection.settimeout(30)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Request must be an object')
            if self.path == '/admin/setup':
                REGISTRY.setup(data['name'], data['password'])
                return self.reply({'configured': True})
            if self.path == '/admin/login':
                with AUTH_LOCK:
                    ATTEMPTS[:] = [t for t in ATTEMPTS if t > time.time() - 60]
                    if len(ATTEMPTS) >= 5:
                        raise ValueError('Too many login attempts; wait one minute')
                    ATTEMPTS.append(time.time())
                    actor = REGISTRY.login(data['password'])
                    ATTEMPTS.clear()
                    for token in list(SESSIONS):
                        if SESSIONS[token]['expires'] < time.time():
                            del SESSIONS[token]
                    token = secrets.token_urlsafe(32)
                    SESSIONS[token] = {'name': actor, 'expires': time.time() + 1800}
                return self.reply({'token': token, 'name': actor})
            if self.path == '/admin/logout':
                with AUTH_LOCK:
                    SESSIONS.pop(self.headers.get('Authorization', '').removeprefix('Bearer '), None)
                return self.reply({'logged_out': True})
            if self.path == '/admin/password':
                self.admin()
                with AUTH_LOCK:
                    REGISTRY.change_password(data['old_password'], data['new_password'])
                    SESSIONS.clear()
                return self.reply({'changed': True})
            if self.path == '/specification/upload':
                raw = base64.b64decode(data['data'], validate=True)
                if len(raw) > 30000000:
                    raise ValueError('Specification exceeds 30 MB')
                with tempfile.TemporaryDirectory(dir=ROOT / 'data') as temporary:
                    path = Path(temporary) / 'candidate.pdf'
                    path.write_bytes(raw)
                    try:
                        parsed = subprocess.run([sys.executable, str(ROOT / 'validate_pdf.py'), str(path)], capture_output=True, timeout=30, encoding='utf-8', errors='replace', creationflags=134217728 if sys.platform == 'win32' else 0)
                    except subprocess.TimeoutExpired:
                        raise ValueError('Specification PDF parsing timed out')
                    if parsed.returncode:
                        raise ValueError('Invalid specification PDF: ' + parsed.stderr[-500:])
                return self.reply({'id': REGISTRY.upload(data, raw), 'status': 'Draft'})
            if self.path == '/specification/transition':
                REGISTRY.transition(int(data['id']), data['action'], self.admin(), data['reason'])
                return self.reply({'updated': True})
            if self.path == '/scanner-profile':
                REGISTRY.set_scanner_profile(data['name'], data['specification_ids'], data.get('description', ''), self.admin())
                return self.reply({'saved': True})
            if self.path == '/inspect':
                ids = data.get('specification_ids')
                if ids is None:
                    ids = [data['specification_id']] if data.get('specification_id') else []
                return self.reply({'job': create_case(data.get('files'), selection(ids))})
            if self.path in ('/properties', '/review'):
                state = STORE.get(data['job'])
                if state['state'] != 'done':
                    raise ValueError('Inspection incomplete')
                analysis = state['result']
                if self.path == '/properties':
                    return self.reply(evaluate_observations(analysis, data.get('observations', [])))
                record = save_review(STORE.path(data['job']), analysis, data)
                return self.reply({'saved': str(STORE.path(data['job'])), 'review': record})
            return self.reply({'error': 'Not found'}, 404)
        except (ValueError, KeyError, TypeError, OSError) as error:
            return self.reply({'error': str(error)}, 400)

def inbox_selection(manifest):
    if 'specification_ids' in manifest:
        return selection(manifest['specification_ids'])
    name = manifest.get('profile')
    profile = next((p for p in REGISTRY.scanner_profiles() if p['name'] == name), None)
    if profile is None:
        raise ValueError('Unknown scanner profile; specify an admin-controlled profile or approved specification_ids')
    return selection(profile['specification_ids'])

def main():
    inbox = Inbox(ROOT / 'inbox', STORE, inbox_selection, create_case)
    threading.Thread(target=inbox.loop, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Offline inspection at http://127.0.0.1:8765. Close this console to stop.')
    threading.Timer(1, lambda: webbrowser.open('http://127.0.0.1:8765')).start()
    server.serve_forever()
if __name__ == '__main__':
    main()
