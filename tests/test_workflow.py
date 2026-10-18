import unittest, sys, tempfile, json, base64, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extraction import extract_candidates, shipping_rows
from reconciliation import reconcile
from selection import combine_specifications
from review import prepare_review
from cases import CaseStore, Inbox
from registry import Registry

def word(text, x, y, width=40):
    return dict(text=text, x=x, y=y, width=width, height=12)

def page(lines, kind='Test report', pid='1:1'):
    return {'id': pid, 'kind': kind, 'file': 'synthetic.pdf', 'number': 1, 'size': [1000, 1400], 'ocr': {'text': '\n'.join((' '.join((w['text'] for w in line)) for line in lines)), 'lines': [{'words': line} for line in lines]}}
RULE = {'property': 'Tensile', 'unit': 'MPa', 'condition': 'TEST', 'clause': 'Synthetic 1', 'min': 100, 'max': 200}

class ExtractionTests(unittest.TestCase):

    def test_labelled_value_is_unverified(self):
        p = page([[word('Tensile:', 10, 10, 90), word('150', 120, 10), word('MPa', 170, 10)], [word('Heat:', 10, 40), word('TEST-HEAT', 70, 40, 100)], [word('Condition:', 10, 70, 100), word('TEST', 130, 70)]])
        c = extract_candidates([p], {'rules': [RULE]})
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]['value'], '150')
        self.assertFalse(c[0]['verified'])
        self.assertEqual(c[0]['heat'], 'TEST-HEAT')

    def test_unitless_values_not_filled_from_spec(self):
        p = page([[word('Tensile:', 10, 10, 90), word('150', 120, 10)]])
        self.assertEqual(extract_candidates([p], {'rules': [RULE]})[0]['unit'], '')

    def test_spec_limit_rows_not_proposed(self):
        p = page([[word('Tensile', 10, 10, 80), word('min', 100, 10), word('100', 150, 10), word('MPa', 220, 10)]])
        self.assertEqual(extract_candidates([p], {'rules': [RULE]}), [])

    def test_horizontal_measured_row(self):
        rule = RULE | {'property': 'Cu', 'unit': '%'}
        p = page([[word('Si', 100, 10), word('Cu', 200, 10), word('Mg', 300, 10)], [word('Actual', 10, 40), word('5.3', 100, 40), word('1.1', 200, 40), word('0.5', 300, 40)]])
        values = extract_candidates([p], {'rules': [rule]})
        self.assertEqual([c['value'] for c in values], ['1.1'])

    def test_absent_adjacent_header_does_not_shift_column(self):
        rule = RULE | {'property': 'Si', 'unit': '%'}
        p = page([[word('Si', 100, 10), word('Cu', 300, 10), word('Mg', 400, 10), word('Zn', 500, 10)], [word('Actual', 10, 40), word('5.3', 100, 40), word('0.04', 200, 40), word('1.1', 300, 40), word('0.5', 400, 40)]])
        self.assertEqual([c['value'] for c in extract_candidates([p], {'rules': [rule]})], ['5.3'])

    def test_duplicate_page_excluded(self):
        p = page([[word('Tensile:', 10, 10, 90), word('150', 120, 10), word('MPa', 170, 10)]])
        p['duplicate'] = 'other'
        self.assertEqual(extract_candidates([p], {'rules': [RULE]}), [])

    def test_inequality_retained(self):
        p = page([[word('Tensile:', 10, 10, 90), word('<150', 120, 10), word('MPa', 170, 10)]])
        self.assertEqual(extract_candidates([p], {'rules': [RULE]})[0]['value'], '<150')

    def test_shipping_requires_explicit_unit(self):
        p = page([[word('3179461-111', 10, 10, 110), word('3', 150, 10), word('EA', 220, 10)]], kind='Shipping')
        self.assertEqual(shipping_rows([p])[0]['quantity'], '3')
        p['duplicate'] = 'copy'
        self.assertEqual(shipping_rows([p]), [])

class ReconciliationTests(unittest.TestCase):

    def test_exact_single_line_matches(self):
        gr = {'id': 'gr', 'kind': 'GR', 'fields': {'Part': '3179461-111', 'Quantity': '3 EA'}}
        ship = {'part': '3179461-111', 'quantity': '3', 'unit': 'EA', 'source_page': 'ship'}
        self.assertEqual(reconcile([gr], [ship])[0]['status'], 'Candidate match')
        self.assertEqual(reconcile([gr], [ship, ship | {'source_page': 'other'}])[0]['status'], 'Needs review')
        self.assertEqual(reconcile([gr], [ship | {'quantity': '4'}])[0]['status'], 'Potential discrepancy')

class SelectionTests(unittest.TestCase):

    def test_independent_revision_rules(self):
        a = {'id': 1, 'code': 'A', 'revision': '1', 'approved_by': 'Admin', 'rules': [RULE]}
        b = {'id': 2, 'code': 'B', 'revision': '2', 'approved_by': 'Admin', 'rules': [RULE | {'max': 180}]}
        combined = combine_specifications([a, b])
        self.assertEqual([r['rule_id'] for r in combined['rules']], ['1:0', '2:0'])
        a['rules'][0]['min'] = 999
        self.assertEqual(combined['rules'][0]['min'], 100)
        a['rules'][0]['min'] = 100

    def test_document_findings_require_resolution(self):
        observation = dict(property='Tensile', value='150', unit='MPa', condition='TEST', heat='H1', source_page='1', verified=True)
        analysis = {'pages': [{'id': '1'}], 'findings': [['Needs review', 'Identity', 'Check', '1']], 'specification': {'status': 'Approved', 'rules': [RULE]}}
        request = dict(inspector='Test', notes='Test', decision='Accepted by inspector', observations=[observation])
        with self.assertRaises(ValueError):
            prepare_review(analysis, request, 'now')
        request['resolutions'] = [{'id': '0', 'resolution': 'Confirmed', 'note': 'Compared source'}]
        self.assertEqual(prepare_review(analysis, request, 'now')['decision'], 'Accepted by inspector')

    def test_multiple_heats_checked_separately(self):
        from properties import compare_properties
        first = dict(property='Tensile', value='150', unit='MPa', condition='TEST', heat='H1', source_page='1', verified=True)
        results = compare_properties({'status': 'Approved', 'rules': [RULE]}, [first, first | {'heat': 'H2', 'value': '250'}])
        self.assertEqual([r['status'] for r in results], ['Within approved limits', 'Outside approved limits'])

class CaseTests(unittest.TestCase):

    def test_worker_persists_and_reopens(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / 'fake_worker.py'
            script.write_text("import json,sys;from pathlib import Path;p=Path(sys.argv[1]);(p/'analysis.json').write_text(json.dumps({'pages':[],'findings':[]}))")
            store = CaseStore(root / 'cases', script)
            job = store.submit([{'name': 'synthetic.pdf', 'data': base64.b64encode(b'%PDF-1.7\nSynthetic').decode()}], None)
            for _ in range(100):
                state = store.get(job)
                if state['state'] in ('done', 'error'):
                    break
                time.sleep(0.05)
            self.assertEqual(state['state'], 'done', state)
            second = CaseStore(root / 'cases', script)
            self.assertEqual(second.get(job)['state'], 'done')
            with self.assertRaises(ValueError):
                store.path('../secret')

    def test_marker_deduplicates_submission(self):

        class Fake:

            def __init__(self):
                self.calls = 0

            def submit(self, *args):
                self.calls += 1
                return 'a' * 32
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch = root / 'delivery'
            batch.mkdir()
            (batch / 'one.pdf').write_bytes(b'%PDF-1.7\nSynthetic')
            (batch / 'READY.json').write_text('{"specification_ids":[1]}')
            fake = Fake()
            inbox = Inbox(root, fake, lambda ids: {'selected': ids})
            inbox.scan_once()
            inbox.scan_once()
            self.assertEqual(fake.calls, 1)

    def test_failed_selection_does_not_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch = root / 'delivery'
            batch.mkdir()
            (batch / 'READY.json').write_text('{"specification_ids":[999]}')

            def fail(ids):
                raise ValueError('Not approved')
            inbox = Inbox(root, None, fail, lambda *args: None)
            inbox.scan_once()
            self.assertEqual(json.loads((batch / 'inspection-status.json').read_text())['error'], 'Not approved')

    def test_reject_non_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CaseStore(Path(temp) / 'cases')
            with self.assertRaises(ValueError):
                store.submit([{'name': 'one.pdf', 'data': base64.b64encode(b'not pdf').decode()}], None)

class AdminTests(unittest.TestCase):

    def test_password_rotation(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Registry(temp)
            registry.setup('Admin', 'old-password-for-test')
            registry.change_password('old-password-for-test', 'new-password-for-test')
            with self.assertRaises(ValueError):
                registry.login('old-password-for-test')
            self.assertEqual(registry.login('new-password-for-test'), 'Admin')

    def test_alias_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Registry(temp)
            with self.assertRaises(ValueError):
                registry.rules([RULE | {'aliases': 'Cu'}])
            registry.rules([RULE | {'aliases': ['UTS']}])

class ScannerProfileTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Registry(self.temp.name)
        self.id = self.registry.upload(dict(code='SYNTHETIC', revision='A', title='Test', applicability='TEST', effective_date='2020-01-01', filename='test.pdf', uploaded_by='Test', rules=[RULE]), b'%PDF-1.7\nSynthetic')

    def tearDown(self):
        self.temp.cleanup()

    def test_draft_cannot_enter_profile(self):
        with self.assertRaises(ValueError):
            self.registry.set_scanner_profile('castings', [self.id], 'Test', 'Admin')

    def test_profile_is_audited_and_revalidates_revision(self):
        self.registry.transition(self.id, 'approve', 'Admin', 'Synthetic fixture')
        self.registry.set_scanner_profile('castings', [self.id], 'Test', 'Admin')
        self.assertEqual(self.registry.scanner_profiles()[0]['specification_ids'], [self.id])
        self.assertEqual(self.registry.history()[0]['action'], 'Scanner profile saved')
        self.registry.transition(self.id, 'withdraw', 'Admin', 'Obsolete test fixture')
        with self.assertRaises(ValueError):
            self.registry.snapshot(self.registry.scanner_profiles()[0]['specification_ids'][0])

    def test_boolean_ids_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.set_scanner_profile('castings', [True], 'Test', 'Admin')

class DocumentOnlyTests(unittest.TestCase):

    def test_required_empty_rules_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Registry(temp)
            sid = registry.upload(dict(code='DOC', revision='A', title='Test', applicability='TEST', effective_date='2020-01-01', filename='test.pdf', uploaded_by='Test', rules=[]), b'%PDF-1.7\nSynthetic')
            with self.assertRaises(ValueError):
                registry.transition(sid, 'approve', 'Admin', 'Test')

    def test_explicit_approved_document_only_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = Registry(temp)
            sid = registry.upload(dict(code='DOC', revision='A', title='Test', applicability='TEST', effective_date='2020-01-01', filename='test.pdf', uploaded_by='Test', rules=[], material_required=False), b'%PDF-1.7\nSynthetic')
            registry.transition(sid, 'approve', 'Admin', 'Document-only scope verified')
            spec = combine_specifications([registry.snapshot(sid)])
            record = prepare_review({'pages': [], 'findings': [], 'specification': spec}, {'inspector': 'Test', 'notes': 'Test scope', 'decision': 'Accepted by inspector'}, 'now')
            self.assertEqual(record['property_results'][0]['status'], 'Not required by approved specification')
if __name__ == '__main__':
    unittest.main()
