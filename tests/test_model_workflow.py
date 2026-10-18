"""Real app HTTP requests with simulated model service responses, no weights needed."""
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import server
from cases import CaseStore
from local_model import propose
from registry import Registry
from worker import write_json

class ModelWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = CaseStore(self.root / 'cases')
        self.registry = Registry(self.root / 'data')
        self.patches = [patch.object(server, 'ROOT', self.root), patch.object(server, 'STORE', self.store), patch.object(server, 'REGISTRY', self.registry)]
        for p in self.patches:
            p.start()
        self.job = 'a' * 32
        self.case = self.root / 'cases' / self.job
        self.case.mkdir()
        self.analysis = {'pages':[{'id':'1:1','kind':'COC','file':'synthetic.pdf','number':1,'image':'1.png',
            'ocr':{'lines':[{'words':[{'text':'UTS: 520 MPa','x':0,'y':0,'width':100,'height':12}]}]}}],
            'findings':[], 'candidates':[], 'specification':{'status':'Approved','rules':[{
                'rule_id':'1:0','property':'UTS','unit':'MPa','condition':'TEST','min':500,'max':600,'clause':'Synthetic 1'}]}}
        write_json(self.case/'status.json', {'state':'done','id':self.job})
        write_json(self.case/'analysis.json', self.analysis)
        write_json(self.root/'data'/'local-model.json', {'enabled':True,'model':'test'})
        server.SESSIONS['test-admin'] = {'name':'Synthetic admin','expires':time.time()+600}
        self.http = server.ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        server.SESSIONS.pop('test-admin', None)
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def request(self, path, data=None, token=''):
        conn = http.client.HTTPConnection('127.0.0.1',self.http.server_address[1],timeout=5)
        conn.request('GET' if data is None else 'POST',path,body=None if data is None else json.dumps(data),
            headers={'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','Content-Type':'application/json','Authorization':'Bearer '+token})
        response = conn.getresponse()
        body = response.read()
        code = response.status
        conn.close()
        return code, body

    def test_model_readiness_is_admin_only(self):
        self.assertEqual(self.request('/local-model/check',{})[0],400)
        with patch.object(server, 'model_status', return_value={'ready':False,'message':'Not installed'}):
            code, body = self.request('/local-model/check',{},'test-admin')
        self.assertEqual(code,200)
        self.assertFalse(json.loads(body)['ready'])

    def test_readiness_failure_does_not_generate_or_change_case(self):
        with patch.object(server, 'model_status', return_value={'ready':False,'message':'Not installed'}), patch.object(server,'propose') as generate:
            self.assertEqual(self.request('/local-model/propose',{'job':self.job,'page':'1:1'})[0],400)
            generate.assert_not_called()
        self.assertEqual(list(self.case.glob('local-model-*.json')), [])
        self.assertEqual(self.store.get(self.job)['result']['candidates'], [])

    def test_proposal_review_recovery_and_evidence_export(self):
        def generate(analysis, config):
            return propose(analysis,config,lambda *_:{'done':True,'message':{'content':json.dumps({'items':[{'rule_id':'1:0','value':'520','unit':'MPa'}]})}})
        with patch.object(server,'model_status',return_value={'ready':True,'digest':'a'*64}), patch.object(server,'propose',side_effect=generate):
            for _ in range(2):
                code, body = self.request('/local-model/propose',{'job':self.job,'page':'1:1'})
                self.assertEqual(code,200)
                self.assertEqual(json.loads(body)['model_digest'],'a'*64)
        # A fresh CaseStore also reopens evidence; repeated suggestions stay deduplicated.
        state = CaseStore(self.root/'cases').get(self.job)
        self.assertEqual(len(state['result']['candidates']),1)
        observation = state['result']['candidates'][0] | {'condition':'TEST','heat':'SYNTHETIC'}
        review = {'job':self.job,'inspector':'Synthetic inspector','notes':'Synthetic test only',
            'decision':'Accepted by inspector','observations':[observation],'resolutions':[]}
        self.assertEqual(self.request('/review',review)[0],400)
        observation['verified'] = True
        self.assertEqual(self.request('/review',review)[0],200)
        code, body = self.request('/case/'+self.job+'/export')
        self.assertEqual(code,200)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            audits = [n for n in archive.namelist() if n.startswith('local-model-')]
            self.assertEqual(len(audits),2)
            correction = json.loads(archive.read('correction-examples.jsonl').splitlines()[-1])
            self.assertTrue(correction['observations'][0]['verified'])
            self.assertEqual(len(correction['model_audits']),2)

    def test_damaged_model_audit_does_not_hide_case(self):
        (self.case/'local-model-broken.json').write_text('{broken',encoding='utf-8')
        state = self.store.get(self.job)
        self.assertEqual(state['state'],'done')
        self.assertTrue(state['result']['model_warnings'])
