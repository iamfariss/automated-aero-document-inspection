import json
import unittest
from local_model import propose, validate_config

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
