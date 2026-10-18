from contextlib import contextmanager
'Local governed specification registry. No network services.'
import sqlite3, hashlib, hmac, secrets, base64, json, math
from pathlib import Path
from datetime import datetime, timezone, timedelta

def now():
    return datetime.now(timezone.utc).isoformat()

def today():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()

class Registry:

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'specifications.sqlite3'
        with self.connect() as c:
            c.executescript("\n   CREATE TABLE IF NOT EXISTS admin(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS specs(id INTEGER PRIMARY KEY,code TEXT NOT NULL,revision TEXT NOT NULL,title TEXT NOT NULL,applicability TEXT NOT NULL,effective_date TEXT NOT NULL,filename TEXT NOT NULL,pdf BLOB NOT NULL,sha256 TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('Draft','Approved','Rejected','Superseded')),uploaded_by TEXT NOT NULL,uploaded_at TEXT NOT NULL,approved_by TEXT,approved_at TEXT,rules TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,spec_id INTEGER,detail TEXT NOT NULL);\n   ")
        with self.connect() as c:
            columns = {row['name'] for row in c.execute('PRAGMA table_info(specs)')}
            if 'material_required' not in columns:
                c.execute('ALTER TABLE specs ADD COLUMN material_required INTEGER NOT NULL DEFAULT 1')
            c.execute('CREATE TABLE IF NOT EXISTS scanner_profiles(name TEXT PRIMARY KEY, specification_ids TEXT NOT NULL, description TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def configured(self):
        with self.connect() as c:
            return c.execute('SELECT 1 FROM admin').fetchone() is not None

    def setup(self, name, password):
        if not name.strip() or len(password) < 12:
            raise ValueError('Admin name and password of at least 12 characters required')
        salt = secrets.token_hex(24)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM admin').fetchone():
                raise ValueError('Admin is already configured')
            c.execute('INSERT INTO admin VALUES(1,?,?,?)', (name.strip(), salt, digest))
            self.audit(c, name.strip(), 'Admin created', None, 'Initial local setup')

    def login(self, password):
        with self.connect() as c:
            r = c.execute('SELECT * FROM admin').fetchone()
        if r is None:
            raise ValueError('Set up the admin first')
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(r['salt']), 600000).hex()
        if not hmac.compare_digest(digest, r['password_hash']):
            raise ValueError('Incorrect admin password')
        return r['name']

    def audit(self, c, actor, action, sid, detail):
        c.execute('INSERT INTO audit(at,actor,action,spec_id,detail) VALUES(?,?,?,?,?)', (now(), actor, action, sid, detail))

    def rules(self, rules):
        if not isinstance(rules, list):
            raise ValueError('Rules must be a JSON array')
        if len(rules) > 100:
            raise ValueError('At most 100 rules per specification')
        for r in rules:
            if not isinstance(r, dict) or not all((str(r.get(k, '')).strip() for k in ['property', 'unit', 'clause', 'condition'])):
                raise ValueError('Each rule needs property, unit, clause/page and material condition')
            if not all((isinstance(r.get(k), str) and r[k].strip() for k in ('property', 'unit', 'clause', 'condition'))):
                raise ValueError('Rule labels must be nonempty text')
            aliases = r.get('aliases', [])
            if not isinstance(aliases, list) or len(aliases) > 20 or any((not isinstance(a, str) or not a.strip() or len(a) > 100 for a in aliases)):
                raise ValueError('Aliases must be up to 20 nonempty text labels')
            limits = [r.get('min'), r.get('max')]
            if all((v is None for v in limits)):
                raise ValueError('Each rule needs min or max')
            if any((v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or (not math.isfinite(v))) for v in limits)):
                raise ValueError('Limits must be finite numbers')
            if all((v is not None for v in limits)) and limits[0] > limits[1]:
                raise ValueError('Minimum exceeds maximum')
        return json.dumps(rules, allow_nan=False)

    def upload(self, d, pdf):
        required = ['code', 'revision', 'title', 'applicability', 'effective_date', 'uploaded_by', 'filename']
        if any((not isinstance(d.get(k), str) or not d[k].strip() for k in required)):
            raise ValueError('Complete all specification metadata fields')
        datetime.strptime(d['effective_date'], '%Y-%m-%d')
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Upload a PDF specification')
        required = d.get('material_required', True)
        if not isinstance(required, bool):
            raise ValueError('Material requirement must be true or false')
        rules = self.rules(d.get('rules', []))
        digest = hashlib.sha256(pdf).hexdigest()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            sid = c.execute('INSERT INTO specs(code,revision,title,applicability,effective_date,filename,pdf,sha256,status,uploaded_by,uploaded_at,rules,material_required) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', tuple((d[k].strip() for k in ['code', 'revision', 'title', 'applicability', 'effective_date', 'filename'])) + (pdf, digest, 'Draft', d['uploaded_by'].strip(), now(), rules, int(required))).lastrowid
            self.audit(c, d['uploaded_by'].strip(), 'Draft uploaded', sid, 'sha256=' + digest)
        return sid

    def list(self):
        with self.connect() as c:
            rows = c.execute('SELECT id,code,revision,title,applicability,effective_date,filename,sha256,status,uploaded_by,uploaded_at,approved_by,approved_at,rules,material_required FROM specs ORDER BY id DESC').fetchall()
        return [dict(r) | {'rules': json.loads(r['rules'])} for r in rows]

    def snapshot(self, sid):
        with self.connect() as c:
            r = c.execute('SELECT * FROM specs WHERE id=?', (sid,)).fetchone()
        if r is None or r['status'] != 'Approved':
            raise ValueError('Only approved specifications may be selected')
        if r['effective_date'] > today():
            raise ValueError('This specification is not yet effective')
        if hashlib.sha256(r['pdf']).hexdigest() != r['sha256']:
            raise ValueError('Specification checksum mismatch')
        d = dict(r)
        d.pop('pdf')
        d['rules'] = json.loads(d['rules'])
        d['material_required'] = bool(d['material_required'])
        return d

    def transition(self, sid, action, actor, reason):
        if not reason.strip():
            raise ValueError('Admin review reason required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r = c.execute('SELECT * FROM specs WHERE id=?', (sid,)).fetchone()
            if r is None:
                raise ValueError('Unknown specification')
            if action in ['approve', 'reject'] and r['status'] != 'Draft':
                raise ValueError('Only a draft can be approved or rejected')
            if action == 'approve':
                if r['material_required'] and (not json.loads(r['rules'])):
                    raise ValueError('Material-required specifications need verified numerical rules before approval')
                if hashlib.sha256(r['pdf']).hexdigest() != r['sha256']:
                    raise ValueError('Specification checksum mismatch')
                if r['effective_date'] > today():
                    raise ValueError('Cannot activate a future-effective specification yet')
                previous = c.execute("SELECT id FROM specs WHERE code=? AND status='Approved'", (r['code'],)).fetchall()
                for old in previous:
                    c.execute("UPDATE specs SET status='Superseded' WHERE id=?", (old['id'],))
                    self.audit(c, actor, 'Superseded', old['id'], f'Replaced by {sid}: {reason}')
                c.execute("UPDATE specs SET status='Approved',approved_by=?,approved_at=? WHERE id=?", (actor, now(), sid))
            elif action == 'reject':
                c.execute("UPDATE specs SET status='Rejected' WHERE id=?", (sid,))
            elif action == 'withdraw':
                if r['status'] != 'Approved':
                    raise ValueError('Only approved specifications can be withdrawn')
                c.execute("UPDATE specs SET status='Superseded' WHERE id=?", (sid,))
            else:
                raise ValueError('Invalid governance action')
            self.audit(c, actor, action, sid, reason)

    def pdf(self, sid):
        with self.connect() as c:
            r = c.execute('SELECT pdf,sha256 FROM specs WHERE id=?', (sid,)).fetchone()
        if not r:
            raise ValueError('Unknown specification')
        if hashlib.sha256(r['pdf']).hexdigest() != r['sha256']:
            raise ValueError('Specification checksum mismatch')
        return r['pdf']

    def history(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC')]

    def change_password(self, old_password, new_password):
        actor = self.login(old_password)
        if not isinstance(new_password, str) or len(new_password) < 12:
            raise ValueError('New password must have at least 12 characters')
        salt = secrets.token_hex(24)
        digest = hashlib.pbkdf2_hmac('sha256', new_password.encode(), bytes.fromhex(salt), 600000).hex()
        with self.connect() as c:
            c.execute('UPDATE admin SET salt=?,password_hash=? WHERE id=1', (salt, digest))
            self.audit(c, actor, 'Password changed', None, 'All admin sessions revoked')

    def scanner_profiles(self):
        with self.connect() as c:
            return [dict(r) | {'specification_ids': json.loads(r['specification_ids'])} for r in c.execute('SELECT * FROM scanner_profiles ORDER BY name')]

    def set_scanner_profile(self, name, ids, description, actor):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('Profile name is required, at most 80 characters')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 8:
            raise ValueError('Select 1-8 approved specifications')
        if any((isinstance(i, bool) or not isinstance(i, (str, int)) for i in ids)):
            raise ValueError('Invalid specification IDs')
        ids = list(dict.fromkeys((int(i) for i in ids)))
        for sid in ids:
            self.snapshot(sid)
        with self.connect() as c:
            c.execute('INSERT INTO scanner_profiles VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET specification_ids=excluded.specification_ids,description=excluded.description,updated_by=excluded.updated_by,updated_at=excluded.updated_at', (name.strip(), json.dumps(ids), str(description).strip(), actor, now()))
            self.audit(c, actor, 'Scanner profile saved', None, json.dumps({'name': name.strip(), 'specification_ids': ids, 'description': str(description)}))
