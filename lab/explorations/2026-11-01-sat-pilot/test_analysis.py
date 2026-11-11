"""Readonly auditor tests: deliberately corrupted traces must be rejected."""
import copy,unittest
from pathlib import Path
from analyze import read,checked_trace,interval,audit_inputs
WORK=Path('E:/ThreeMindData/experiments/2026-11-01-sat-pilot/v1')
@unittest.skipUnless((WORK/"origins/o0/intact/result-000.json.gz").exists(), "requires local frozen original")
class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material=read(WORK/'material/o0.json')['tests'][0]
        cls.trace=read(WORK/'origins/o0/intact/result-000.json.gz')
        cls.mapping=read(WORK/'origins/o0/intact/whole-000.json.gz')['mapping']
    def test_real_trace_and_wrong_witness(self):
        checked_trace(self.material,self.trace,self.mapping)
        t=copy.deepcopy(self.trace);t['solved']=not t['solved']
        with self.assertRaises(AssertionError):checked_trace(self.material,t,self.mapping)
    def test_wrong_break_rejected(self):
        t=copy.deepcopy(self.trace);t['steps'][0]['breaks'][0]+=1
        with self.assertRaises(AssertionError):checked_trace(self.material,t,self.mapping)
    def test_wrong_anonymous_input_rejected(self):
        t=copy.deepcopy(self.trace);t['steps'][0]['queries'][0]['input']['channels'][0][1]=.1
        with self.assertRaises(AssertionError):checked_trace(self.material,t,self.mapping)
    def test_wrong_flip_rejected(self):
        t=copy.deepcopy(self.trace);t['steps'][0]['assignment'][0]=not t['steps'][0]['assignment'][0]
        with self.assertRaises(AssertionError):checked_trace(self.material,t,self.mapping)
    def test_full_input_chain_and_hidden_input_rejected(self):
        previous=read(WORK/'origins/o0/intact/whole-000.json.gz')
        after=read(WORK/'origins/o0/intact/whole-001.json.gz')
        audit_inputs(previous,self.trace,after)
        after['input_digest']='0'*64
        with self.assertRaises(AssertionError):audit_inputs(previous,self.trace,after)
    def test_interval_determinism(self):
        self.assertEqual(interval([0]*8),[0,0])
        self.assertEqual(interval([.1]*8),[.1,.1])
if __name__=='__main__':unittest.main()
