import copy,unittest
import numpy as np
import analyze as a
from student import load,FRAME_INDEX
class Arithmetic(unittest.TestCase):
 def test_constant_origin_interval(self):
  r=a.ci([.25]*8)
  self.assertEqual(r['mean'],.25);self.assertEqual(r['ci975'],[.25,.25])
 def test_known_witness_and_break(self):
  f={'n':3,'clauses':[[1,2,3],[-1,2,-3]]};x=[True,False,False]
  self.assertTrue(a.good(f,x));self.assertEqual(a.broken(f,x,0),1)
 def test_real_first_student_and_corruption(self):
  folder=a.d.WORK/'origins/o0/normal';s=load(folder/'whole-birth.json.gz');c=a.InputChain(s)
  teach=load(folder/'teaching-0.json.gz')
  for r in teach['lessons']:c.lesson(r)
  q=load(folder/'samples-0.json.gz')[0]['question'];broken=copy.deepcopy(q);broken['end_us']+=1
  with self.assertRaises(AssertionError):c.question(broken)
  q2=copy.deepcopy(q);q2['input']['channels'][0][0]+=1
  with self.assertRaises(AssertionError):c.question(q2)
  c.question(q)
 def test_changed_witness_rejected(self):
  m=load(a.d.WORK/'material/o0.json');f=a.d.WORK/'origins/o0/normal'
  r=load(f/'result-000.json.gz');a.audit_result(m['tests'][0],r)
  bad=copy.deepcopy(r);bad['solved']=not r['solved']
  with self.assertRaises(AssertionError):a.audit_result(m['tests'][0],bad)
if __name__=='__main__':unittest.main(verbosity=2)
