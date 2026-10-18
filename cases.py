"""Persistent case queue and completed-batch inbox. All work stays local."""
import base64, hashlib, json, re, subprocess, sys, threading, queue, uuid
from pathlib import Path
from datetime import datetime, timezone
from worker import write_json

class CaseStore:

    def __init__(self, root, worker_script=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.worker_script = worker_script or Path(__file__).with_name('worker.py')
        self.lock = threading.RLock()
        self.pending = queue.Queue(maxsize=8)
        for analysis in self.root.glob('*/analysis.json'):
            if not (analysis.parent / 'status.json').exists():
                try:
                    saved = json.loads(analysis.read_text(encoding='utf-8'))
                    write_json(analysis.parent / 'status.json', {'id': analysis.parent.name, 'state': 'done', 'created': datetime.fromtimestamp(analysis.stat().st_mtime, timezone.utc).isoformat(), 'origin': 'Imported earlier version', 'files': list(dict.fromkeys((p['file'] for p in saved['pages'])))})
                except (ValueError, KeyError):
                    pass
        for path in self.root.glob('*/status.json'):
            try:
                status = json.loads(path.read_text(encoding='utf-8'))
                if status['state'] in ('queued', 'running'):
                    status.update(state='error', error='Interrupted by app restart. Resubmit the source documents.')
                    write_json(path, status)
            except (ValueError, KeyError):
                continue
        threading.Thread(target=self.loop, daemon=True).start()

    def path(self, job):
        if not isinstance(job, str) or not re.fullmatch('[a-f0-9]{32}', job):
            raise ValueError('Invalid case identifier')
        path = self.root / job
        if not path.is_dir():
            raise ValueError('Unknown case')
        return path

    def submit(self, files, specification, origin='Manual upload', attachments=None):
        if not isinstance(files, list) or not 1 <= len(files) <= 30:
            raise ValueError('Select 1 to 30 PDF files')
        payload = []
        total = 0
        for index, item in enumerate(files, 1):
            name = Path(item['name']).name
            if not name.lower().endswith('.pdf') or len(name) > 240:
                raise ValueError('Only PDF filenames are accepted')
            raw = base64.b64decode(item['data'], validate=True)
            total += len(raw)
            if not raw.startswith(b'%PDF-') or total > 100000000:
                raise ValueError('Invalid PDF or batch exceeds 100 MB')
            payload.append((index, name, raw))
        with self.lock:
            if self.pending.full():
                raise ValueError('Inspection queue is full; try again after a case finishes')
            job = uuid.uuid4().hex
            case = self.root / job
            case.mkdir()
            documents = []
            for index, name, raw in payload:
                stored = f'source_{index}.pdf'
                (case / stored).write_bytes(raw)
                documents.append({'index': index, 'name': name, 'stored': stored, 'sha256': hashlib.sha256(raw).hexdigest()})
            write_json(case / 'request.json', {'documents': documents, 'specification': specification})
            write_json(case / 'status.json', {'id': job, 'state': 'queued', 'created': datetime.now(timezone.utc).isoformat(), 'origin': origin, 'files': [p[1] for p in payload]})
            for name, raw in (attachments or {}).items():
                if not re.fullmatch('specification_\\d+\\.pdf', name):
                    raise ValueError('Invalid specification archive name')
                (case / name).write_bytes(raw)
            self.pending.put_nowait(job)
            return job

    def get(self, job):
        case = self.path(job)
        with self.lock:
            status = json.loads((case / 'status.json').read_text(encoding='utf-8'))
        if status['state'] == 'done':
            status['result'] = json.loads((case / 'analysis.json').read_text(encoding='utf-8'))
            for audit_path in sorted(case.glob('local-model-*.json')):
                audit = json.loads(audit_path.read_text(encoding='utf-8'))
                status['result'].setdefault('candidates', []).extend(audit.get('candidates', []))
            history = case / 'review-history.jsonl'
            if history.exists():
                status['review'] = json.loads(history.read_text(encoding='utf-8').splitlines()[-1])
        elif (case / 'progress.json').exists():
            try:
                status.update(json.loads((case / 'progress.json').read_text(encoding='utf-8')))
            except ValueError:
                pass
        return status

    def list(self):
        result = []
        for path in self.root.glob('*/status.json'):
            try:
                status = json.loads(path.read_text(encoding='utf-8'))
                history = path.parent / 'review-history.jsonl'
                if history.exists():
                    status['decision'] = json.loads(history.read_text(encoding='utf-8').splitlines()[-1])['decision']
                result.append(status)
            except (ValueError, KeyError):
                continue
        return sorted(result, key=lambda c: c['created'], reverse=True)

    def loop(self):
        while True:
            job = self.pending.get()
            try:
                case = self.path(job)
                with self.lock:
                    status = json.loads((case / 'status.json').read_text(encoding='utf-8'))
                    status.update(state='running')
                    write_json(case / 'status.json', status)
                completed = subprocess.run([sys.executable, str(self.worker_script), str(case)], capture_output=True, timeout=900, encoding='utf-8', errors='replace', creationflags=134217728 if sys.platform == 'win32' else 0)
                if completed.returncode:
                    raise ValueError(completed.stderr.strip()[-2000:] or 'PDF processing failed')
                if not (case / 'analysis.json').exists():
                    raise ValueError('Worker produced no analysis')
                status.update(state='done')
            except Exception as error:
                status.update(state='error', error=str(error))
            finally:
                with self.lock:
                    write_json(case / 'status.json', status)
                self.pending.task_done()

class Inbox:

    def __init__(self, root, store, snapshot_selection, submit=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = store
        self.snapshot_selection = snapshot_selection
        self.submit = submit or store.submit

    def scan_once(self):
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.is_symlink() or (not folder.resolve().is_relative_to(self.root.resolve())):
                continue
            marker = folder / 'READY.json'
            if not marker.is_file() or marker.is_symlink():
                continue
            report = folder / 'inspection-status.json'
            if marker.stat().st_size > 10000:
                continue
            signature = str(marker.stat().st_mtime_ns)
            if report.exists():
                try:
                    if json.loads(report.read_text(encoding='utf-8')).get('marker') == signature:
                        continue
                except ValueError:
                    pass
            try:
                manifest = json.loads(marker.read_text(encoding='utf-8'))
                selected = self.snapshot_selection(manifest)
                pdfs = sorted(folder.glob('*.pdf'))
                if not 1 <= len(pdfs) <= 30 or sum((p.stat().st_size for p in pdfs)) > 100000000:
                    raise ValueError('Completed batch must contain 1-30 PDFs, at most 100 MB')
                if any((p.is_symlink() or not p.resolve().is_relative_to(folder.resolve()) for p in pdfs)):
                    raise ValueError('Linked source files are not accepted')
                files = [{'name': p.name, 'data': base64.b64encode(p.read_bytes()).decode()} for p in pdfs]
                job = self.submit(files, selected, 'Scanner inbox: ' + folder.name)
                write_json(report, {'marker': signature, 'case': job, 'state': 'submitted'})
            except Exception as error:
                write_json(report, {'marker': signature, 'state': 'error', 'error': str(error)})

    def loop(self):
        while True:
            try:
                self.scan_once()
            except OSError:
                pass
            threading.Event().wait(5)
