import json
import unittest
from local_model import propose, validate_config, model_status, local_request
from unittest.mock import patch, MagicMock

class LocalModelTests(unittest.TestCase):
    def analysis(self, content='UTS: 520 MPa'):
        return {'specification': {'rules': [{'rule_id': '1:0', 'property': 'tensile strength', 'aliases': ['UTS']}]},
            'pages': [{'id': '1:1', 'kind': 'COC', 'ocr': {'lines': [{'words': [
                {'text': content, 'x': 1, 'y': 2, 'width': 100, 'height': 20}]}]}}]}

    def response(self, items):
        return lambda *_: {'model': 'test', 'message': {'content': json.dumps({'items': items})}}

    def test_grounded_proposal_is_unverified_without_inferred_heat(self):
        a = propose(self.analysis(), {'enabled': True, 'model': 'test'}, self.response([
            {'rule_id': '1:0', 'value': '520', 'unit': 'MPa'}]))
        self.assertFalse(a['candidates'][0]['verified'])
        self.assertEqual(a['candidates'][0]['heat'], '')
        self.assertIn('request', a['calls'][0])
        self.assertIn('response', a['calls'][0])

    def test_hallucinated_digit_unit_rule_and_extra_fields_rejected(self):
        items = [{'rule_id': '1:0', 'value': '52', 'unit': 'MPa'},
                 {'rule_id': '1:0', 'value': '520', 'unit': 'psi'},
                 {'rule_id': 'other', 'value': '520', 'unit': 'MPa'},
                 {'rule_id': '1:0', 'value': '520', 'unit': 'MPa', 'verified': True}]
        a = propose(self.analysis(), {'enabled': True, 'model': 'test'}, self.response(items))
        self.assertEqual(a['candidates'], [])
        self.assertEqual(a['calls'][0]['rejected'], 4)

    def test_limits_and_inequalities_do_not_become_measured_values(self):
        for content in ('UTS minimum 520 MPa', 'UTS: >520 MPa', 'UTS: > 520 MPa', 'UTS: -520 MPa', 'UTS: 1520 MPa'):
            a = propose(self.analysis(content), {'enabled': True, 'model': 'test'},
                self.response([{'rule_id': '1:0', 'value': '520', 'unit': 'MPa'}]))
            self.assertEqual(a['candidates'], [])

    def test_disabled_never_calls_model(self):
        def fail(*_):
            self.fail('Network called')
        self.assertEqual(propose(self.analysis(), {}, fail)['calls'], [])

    def test_outage_preserves_analysis(self):
        def fail(*_):
            raise OSError('Offline model unavailable')
        a = propose(self.analysis(), {'enabled': True, 'model': 'test'}, fail)
        self.assertIn('error', a['calls'][0])
        self.assertEqual(a['candidates'], [])

    def test_config_rejects_invalid_types(self):
        with self.assertRaises(ValueError):
            validate_config({'enabled': 'yes', 'model': 'test'})
        self.assertEqual(validate_config({'enabled': True, 'model': 'qwen3:0.6b'})['model'], 'qwen3:0.6b')

    def test_ambiguous_row_and_unpaired_unit_rejected(self):
        for row in ('UTS: 520; YS: 400 MPa', 'UTS: 520; MPa listed elsewhere'):
            self.assertEqual(propose(self.analysis(row), {'enabled': True, 'model': 'test'},
                self.response([{'rule_id': '1:0', 'value': '520', 'unit': 'MPa'}]))['candidates'], [])

    def test_duplicate_model_items_collapsed(self):
        item = {'rule_id': '1:0', 'value': '520', 'unit': 'MPa'}
        self.assertEqual(len(propose(self.analysis(), {'enabled': True, 'model': 'test'}, self.response([item,item]))['candidates']), 1)

    def test_incomplete_generation_rejected(self):
        response = self.response([{'rule_id': '1:0', 'value': '520', 'unit': 'MPa'}])()
        response['done_reason'] = 'length'
        audit = propose(self.analysis(), {'enabled': True, 'model': 'test'}, lambda *_: response)
        self.assertEqual(audit['candidates'], [])
        self.assertIn('incomplete', audit['calls'][0]['error'])

    def test_budget_stops_before_generation(self):
        times = iter([0, 61])
        audit = propose(self.analysis(), {'enabled': True, 'model': 'test'}, clock=lambda: next(times))
        self.assertTrue(audit['truncated'])
        self.assertEqual(audit['calls'], [])

    def test_readiness_records_installed_digest(self):
        state = model_status({'model':'test'}, lambda *a, **kw: {'models':[{'name':'test','digest':'a'*64,'size':123}]})
        self.assertTrue(state['ready'])
        self.assertEqual(state['digest'], 'a'*64)

    def test_readiness_blocks_missing_cloud_and_unreachable(self):
        for models in ([], [{'name':'test','digest':'a'*64,'remote_host':'cloud.example'}], [{'name':'test','digest':'bad'}]):
            self.assertFalse(model_status({'model':'test'}, lambda *a, **kw: {'models':models})['ready'])
        def unavailable(*a, **kw):
            raise OSError('unavailable')
        self.assertFalse(model_status({'model':'test'}, unavailable)['ready'])

    def test_transport_is_bounded_and_ignores_proxies(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'x' * 131073
        with patch('local_model.urllib.request.build_opener', return_value=opener) as build:
            with self.assertRaisesRegex(ValueError, 'too large'):
                local_request('/api/chat', {})
            self.assertEqual(build.call_args.args[0].proxies, {})
            self.assertEqual(opener.open.call_args.args[0].full_url, 'http://127.0.0.1:11434/api/chat')
        with self.assertRaises(ValueError):
            local_request('https://external.example')
