import unittest, tempfile, sys, threading, json, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry import Registry
from properties import compare_properties
RULE = {'property': 'Example test property', 'unit': 'MPa', 'condition': 'TEST ONLY', 'clause': 'Test clause 1', 'min': 100, 'max': 200}

class RegistryTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.r = Registry(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, revision='A'):
        return self.r.upload(dict(code='TEST-SPEC', revision=revision, title='Synthetic specification', applicability='TEST ONLY', effective_date='2020-01-01', filename='test.pdf', uploaded_by='Uploader', rules=[RULE]), b'%PDF-1.7\nSynthetic database test fixture')

    def test_setup_and_login(self):
        self.r.setup('Admin', 'long-password-for-tests')
        self.assertEqual(self.r.login('long-password-for-tests'), 'Admin')
        with self.assertRaises(ValueError):
            self.r.login('wrong')
        with self.assertRaises(ValueError):
            self.r.setup('Other', 'another-long-password')

    def test_draft_cannot_be_used(self):
        sid = self.upload()
        with self.assertRaises(ValueError):
            self.r.snapshot(sid)

    def test_replacement_preserves_snapshot(self):
        a = self.upload()
        self.r.transition(a, 'approve', 'Admin', 'Reviewed')
        old = self.r.snapshot(a)
        b = self.upload('B')
        self.r.transition(b, 'approve', 'Admin', 'Replacement checked')
        self.assertEqual(old['revision'], 'A')
        self.assertEqual(old['status'], 'Approved')
        with self.assertRaises(ValueError):
            self.r.snapshot(a)
        self.assertEqual(self.r.snapshot(b)['revision'], 'B')
        self.assertEqual(len(self.r.history()), 5)

    def test_reason_required(self):
        with self.assertRaises(ValueError):
            self.r.transition(self.upload(), 'approve', 'Admin', '')

    def test_rejection_cannot_be_approved(self):
        sid = self.upload()
        self.r.transition(sid, 'reject', 'Admin', 'Wrong content')
        with self.assertRaises(ValueError):
            self.r.transition(sid, 'approve', 'Admin', 'Attempt')

    def test_future_date(self):
        sid = self.upload()
        with self.r.connect() as c:
            c.execute("UPDATE specs SET effective_date='2999-01-01' WHERE id=?", (sid,))
        with self.assertRaises(ValueError):
            self.r.transition(sid, 'approve', 'Admin', 'Future')

    def test_bad_limits(self):
        for rule in [RULE | {'min': 300}, RULE | {'max': float('nan')}, RULE | {'unit': ''}, RULE | {'min': None, 'max': None}]:
            with self.assertRaises(ValueError):
                self.r.rules([rule])

    def test_tamper_detected(self):
        sid = self.upload()
        self.r.transition(sid, 'approve', 'Admin', 'Checked')
        with self.r.connect() as c:
            c.execute('UPDATE specs SET pdf=? WHERE id=?', (b'changed', sid))
        with self.assertRaises(ValueError):
            self.r.snapshot(sid)

    def test_withdrawal(self):
        sid = self.upload()
        self.r.transition(sid, 'approve', 'Admin', 'Checked')
        self.r.transition(sid, 'withdraw', 'Admin', 'Obsolete')
        with self.assertRaises(ValueError):
            self.r.snapshot(sid)

class PropertyTests(unittest.TestCase):

    def check(self, value=150, **changes):
        observation = dict(property=RULE['property'], condition=RULE['condition'], unit='MPa', value=value, source_page='test:1', heat='TEST-HEAT', verified=True) | changes
        return compare_properties({'status': 'Approved', 'rules': [RULE]}, [observation])[0]['status']

    def test_boundaries(self):
        for v in [100, 150, 200]:
            self.assertEqual(self.check(v), 'Within approved limits')
        for v in [99.99, 200.01]:
            self.assertEqual(self.check(v), 'Outside approved limits')

    def test_no_conversion(self):
        self.assertEqual(self.check(unit='psi'), 'Needs review')

    def test_no_unverified_pass(self):
        self.assertEqual(self.check(verified=False), 'Needs review')

    def test_traceability_required(self):
        self.assertEqual(self.check(heat=''), 'Needs review')

    def test_nan(self):
        self.assertEqual(self.check(value='NaN'), 'Needs review')

    def test_missing_rules(self):
        self.assertEqual(compare_properties({'status': 'Approved', 'rules': []}, [])[0]['status'], 'Needs review')

class EndpointTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import server
        cls.module = server
        cls.temp = tempfile.TemporaryDirectory()
        server.REGISTRY = Registry(cls.temp.name)
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.temp.cleanup()

    def request(self, path, payload, token='', origin='http://127.0.0.1:8765'):
        req = urllib.request.Request('http://127.0.0.1:' + str(self.http.server_address[1]) + path, data=json.dumps(payload).encode(), headers={'Host': '127.0.0.1:8765', 'Content-Type': 'application/json', 'Origin': origin, 'Authorization': 'Bearer ' + token})
        try:
            with urllib.request.urlopen(req) as response:
                return (response.status, json.load(response))
        except urllib.error.HTTPError as e:
            return (e.code, json.load(e))

    def test_governance_requires_admin(self):
        status, data = self.request('/specification/transition', {'id': 1, 'action': 'approve', 'reason': 'Attempt'})
        self.assertEqual(status, 400)
        self.assertIn('Admin login required', data['error'])

    def test_bad_origin(self):
        self.assertEqual(self.request('/admin/setup', {}, origin='https://example.com')[0], 403)

    def test_login_logout(self):
        self.assertEqual(self.request('/admin/setup', {'name': 'Admin', 'password': 'long-password-for-tests'})[0], 200)
        status, data = self.request('/admin/login', {'password': 'long-password-for-tests'})
        self.assertEqual(status, 200)
        token = data['token']
        self.assertEqual(self.request('/admin/logout', {}, token)[0], 200)
        self.assertEqual(self.request('/specification/transition', {'id': 1, 'action': 'approve', 'reason': 'Attempt'}, token)[0], 400)
if __name__ == '__main__':
    unittest.main()
