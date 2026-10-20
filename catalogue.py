"""Local reference catalogue; never makes a source an approved specification."""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from contextlib import contextmanager

class Catalogue:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / 'files').mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'catalogue.sqlite3'
        with self.connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, archive_sha TEXT NOT NULL,
                  member TEXT NOT NULL, family TEXT NOT NULL, extension TEXT NOT NULL, size INTEGER NOT NULL,
                  sha256 TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                  pages INTEGER, indexed_pages INTEGER, text TEXT NOT NULL DEFAULT '',
                  UNIQUE(archive_sha,member));
                CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(member,family,text);
                CREATE TABLE IF NOT EXISTS imports(sha256 TEXT PRIMARY KEY, filename TEXT NOT NULL,
                  imported_at TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
            ''')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def import_zip(self, archive, progress=lambda value: None):
        """Stream PDFs into hash-addressed storage. Other formats are inventory only."""
        archive = Path(archive)
        with archive.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        with zipfile.ZipFile(archive) as z, self.connect() as c:
            entries = [i for i in z.infolist() if not i.is_dir()]
            if len(entries) > 20000 or sum(i.file_size for i in entries) > 5_000_000_000:
                raise ValueError('Archive exceeds catalogue limits')
            names = set()
            for item in entries:
                member = PurePosixPath(item.filename.replace('\\', '/'))
                if member.is_absolute() or '..' in member.parts or ':' in str(member) or '\x00' in str(member):
                    raise ValueError('Unsafe archive member path')
                if str(member) in names:
                    raise ValueError('Duplicate archive member path')
                names.add(str(member))
                if item.file_size > 200_000_000 or item.flag_bits & 1:
                    raise ValueError('Encrypted or oversized archive member')
            c.execute('INSERT OR IGNORE INTO imports VALUES(?,?,?,0)', (digest, archive.name, datetime.now(timezone.utc).isoformat()))
            c.commit()
            for index, item in enumerate(entries):
                member = str(PurePosixPath(item.filename.replace('\\', '/')))
                if c.execute('SELECT 1 FROM sources WHERE archive_sha=? AND member=?', (digest, member)).fetchone():
                    continue
                extension = PurePosixPath(member).suffix.lower()
                h = hashlib.sha256()
                # No archive path is used as a filesystem destination.
                import tempfile
                with tempfile.TemporaryFile(dir=self.root) as temporary, z.open(item) as source:
                    count = 0
                    while block := source.read(1024 * 1024):
                        count += len(block)
                        if count > 200_000_000 or count > item.file_size:
                            raise ValueError('Expanded member exceeds declared size')
                        h.update(block)
                        if extension == '.pdf':
                            temporary.write(block)
                    if count != item.file_size:
                        raise ValueError('Archive member length mismatch')
                    sha = h.hexdigest()
                    status = 'Unsupported format — inventory only'
                    if extension == '.pdf':
                        temporary.seek(0)
                        if temporary.read(5) != b'%PDF-':
                            status = 'Invalid PDF header'
                        else:
                            target = self.root / 'files' / (sha + '.pdf')
                            if not target.exists():
                                temporary.seek(0)
                                import shutil
                                with target.open('wb') as output:
                                    shutil.copyfileobj(temporary, output)
                            status = 'Pending text index'
                family = PurePosixPath(member).parts[1] if len(PurePosixPath(member).parts) > 2 else ''
                cursor = c.execute('INSERT INTO sources(archive_sha,member,family,extension,size,sha256,status) VALUES(?,?,?,?,?,?,?)',
                    (digest, member, family, extension, count, sha, status))
                c.execute('INSERT INTO search(rowid,member,family,text) VALUES(?,?,?,?)', (cursor.lastrowid, member, family, ''))
                if index % 50 == 0:
                    c.commit()
                    progress({'stage':'Importing', 'processed':index+1, 'total':len(entries)})
            c.execute('UPDATE imports SET completed=1 WHERE sha256=?', (digest,))
        return self.summary()

    def index(self, progress=lambda value: None):
        """Index up to three native-text pages in bounded child batches; no OCR here."""
        with self.connect() as c:
            pending = c.execute("SELECT id,sha256 FROM sources WHERE status='Pending text index'").fetchall()
        for offset in range(0, len(pending), 20):
            batch = pending[offset:offset+20]
            request = [{'id':r['id'], 'path':str((self.root/'files'/(r['sha256']+'.pdf')).resolve())} for r in batch]
            try:
                run = subprocess.run([sys.executable, str(Path(__file__).with_name('catalogue_worker.py'))],
                    input=json.dumps(request), capture_output=True, encoding='utf-8', errors='replace', timeout=30,
                    creationflags=134217728 if sys.platform == 'win32' else 0)
                if run.returncode:
                    raise ValueError('PDF indexing worker failed')
                results = json.loads(run.stdout)
            except (ValueError, subprocess.TimeoutExpired):
                results = [{'id':r['id'], 'status':'PDF indexing error', 'detail':'Worker failed or exceeded 30-second batch limit'} for r in batch]
            with self.connect() as c:
                for r in results:
                    c.execute('UPDATE sources SET status=?,detail=?,pages=?,indexed_pages=?,text=? WHERE id=?',
                        (r['status'],r.get('detail',''),r.get('pages'),r.get('indexed_pages'),r.get('text',''),r['id']))
                    c.execute('UPDATE search SET text=? WHERE rowid=?',(r.get('text',''),r['id']))
            progress({'stage':'Indexing', 'processed':min(offset+20,len(pending)), 'total':len(pending)})
        return self.summary()

    def summary(self):
        with self.connect() as c:
            return {'total':c.execute('SELECT count(*) FROM sources').fetchone()[0],
                'unique_pdfs':c.execute("SELECT count(DISTINCT sha256) FROM sources WHERE extension='.pdf' AND status!='Invalid PDF header'").fetchone()[0],
                'statuses':{r[0]:r[1] for r in c.execute('SELECT status,count(*) FROM sources GROUP BY status')},
                'families':{r[0]:r[1] for r in c.execute('SELECT family,count(*) FROM sources GROUP BY family')},
                'approval':'All catalogue entries are unreviewed references, not approved requirements.'}

    def search(self, query='', offset=0):
        if not isinstance(query, str) or len(query)>200 or not 0 <= offset <= 20000:
            raise ValueError('Invalid catalogue search')
        tokens = re.findall(r'\w+',query, re.UNICODE)[:8]
        with self.connect() as c:
            if tokens:
                expression = ' AND '.join('"'+t+'"*' for t in tokens)
                total = c.execute('SELECT count(*) FROM search WHERE search MATCH ?', (expression,)).fetchone()[0]
                rows = c.execute('''SELECT s.id,s.member,s.family,s.extension,s.size,s.sha256,s.status,s.detail,s.pages,s.indexed_pages,
                    snippet(search,2,'[',']',' … ',32) AS excerpt FROM search JOIN sources s ON s.id=search.rowid
                    WHERE search MATCH ? ORDER BY rank LIMIT 30 OFFSET ?''',(expression,offset)).fetchall()
            else:
                total=c.execute('SELECT count(*) FROM sources').fetchone()[0]
                rows=c.execute("SELECT id,member,family,extension,size,sha256,status,detail,pages,indexed_pages,'' AS excerpt FROM sources ORDER BY member LIMIT 30 OFFSET ?",(offset,)).fetchall()
        return {'total':total,'offset':offset,'items':[dict(r) for r in rows], 'scope':'Filename and first three native-text PDF pages only. Scanned text is not indexed.'}

    def pdf(self, source_id):
        with self.connect() as c:
            row=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
        if row is None or row['extension']!='.pdf' or row['status']=='Invalid PDF header':
            raise ValueError('Catalogue PDF not available')
        raw=(self.root/'files'/(row['sha256']+'.pdf')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Catalogue source checksum mismatch')
        return dict(row),raw
