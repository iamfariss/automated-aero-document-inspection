import unittest,sys,tempfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review import evaluate_observations, prepare_review

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.analysis={'pages':[{'id':'1:1'}],'specification':{'id':1,'code':'SYNTHETIC','revision':'A','status':'Approved','rules':[{'property':'Tensile','condition':'TEST','unit':'MPa','clause':'test 1','min':100,'max':200}]}}
        self.observation={'property':'Tensile','condition':'TEST','unit':'MPa','value':'150','heat':'TEST-HEAT','source_page':'1:1','verified':True}
        self.request={'inspector':'Test inspector','notes':'Synthetic test','decision':'Accepted by inspector','observations':[self.observation]}
    def test_verified_result_saved_with_evidence(self):
        record=prepare_review(self.analysis,self.request,'2026-10-18T10:00:00+08:00')
        self.assertEqual(record['property_results'][0]['status'],'Within approved limits')
        self.assertEqual(record['observations'][0]['source_page'],'1:1')
        self.assertEqual(record['specification']['revision'],'A')
    def test_foreign_page_rejected(self):
        self.observation['source_page']='other-case:1'
        with self.assertRaises(ValueError):evaluate_observations(self.analysis,[self.observation])
    def test_unverified_acceptance_rejected(self):
        self.observation['verified']=False
        with self.assertRaises(ValueError):prepare_review(self.analysis,self.request,'now')
    def test_out_of_limit_acceptance_rejected(self):
        self.observation['value']='201'
        with self.assertRaises(ValueError):prepare_review(self.analysis,self.request,'now')
    def test_rejection_can_record_failure(self):
        self.observation['value']='201';self.request['decision']='Rejected by inspector'
        record=prepare_review(self.analysis,self.request,'now')
        self.assertEqual(record['property_results'][0]['status'],'Outside approved limits')
    def test_missing_requirements_cannot_be_accepted(self):
        self.analysis['specification']=None
        with self.assertRaises(ValueError):prepare_review(self.analysis,self.request,'now')
    def test_client_results_not_trusted(self):
        self.observation['value']='250';self.request['property_results']=[{'status':'Within approved limits'}]
        with self.assertRaises(ValueError):prepare_review(self.analysis,self.request,'now')
    def test_whitespace_evidence_not_verified(self):
        self.observation['heat']='  '
        self.assertEqual(evaluate_observations(self.analysis,[self.observation])['results'][0]['status'],'Needs review')
    def test_duplicates_require_review(self):
        self.assertEqual(evaluate_observations(self.analysis,[self.observation,self.observation])['results'][0]['status'],'Needs review')
    def test_invalid_payload(self):
        for payload in [None,{},[None],[{'value':True}]]:
            with self.assertRaises(ValueError):evaluate_observations(self.analysis,payload)

if __name__=='__main__':unittest.main()
