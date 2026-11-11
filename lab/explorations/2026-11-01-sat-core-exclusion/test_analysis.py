import unittest
import analyze as a
class Arithmetic(unittest.TestCase):
 def test_witness(self):
  self.assertTrue(a.valid([[1,2,3]], [True,False,False]))
  self.assertFalse(a.valid([[1,2,3]], [False,False,False]))
 def test_break_count(self):
  self.assertEqual(a.broken([[1,2,3],[-1,2,3]],[True,False,False],0),1)
  self.assertEqual(a.broken([[1,2,3]],[True,True,False],0),0)
 def test_exact_equivalence(self):
  self.assertEqual(a.confidence([0]*8)['interval'],[0,0])
 def test_gain_interval(self):
  r=a.confidence([.2]*8,.95)
  self.assertAlmostEqual(r['mean'],.2)
  self.assertTrue(all(abs(x-.2)<1e-12 for x in r['interval']))
if __name__=='__main__':unittest.main()
