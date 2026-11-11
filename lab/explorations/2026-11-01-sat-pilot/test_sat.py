"""Independent arithmetic and API-boundary checks for the SAT apparatus."""
import itertools
import random
import unittest
import sat_problem as p

class SATChecks(unittest.TestCase):
    def test_dpll_against_exhaustion(self):
        rng=random.Random(981)
        for n in (3,4,5,6):
            for _ in range(30):
                clauses=[tuple(v if rng.getrandbits(1) else -v for v in rng.sample(range(1,n+1),3))
                         for _ in range(4*n)]
                expected=any(p.verify_witness(n,clauses,list(a)) for a in itertools.product((False,True),repeat=n))
                result=p.solve_exact(n,clauses)
                self.assertEqual(result["satisfiable"],expected)
                if expected:self.assertTrue(p.verify_witness(n,clauses,result["witness"]))
    def test_break_count_by_full_evaluation(self):
        rng=random.Random(982)
        for _ in range(50):
            n=6;c=[tuple(v if rng.getrandbits(1) else -v for v in rng.sample(range(1,n+1),3)) for _ in range(20)]
            a=[bool(rng.getrandbits(1)) for _ in range(n)]
            old=set(p.unsatisfied(c,a))
            for v in range(n):
                b=a[:];b[v]=not b[v]
                self.assertEqual(p.break_count(c,a,v),len(set(p.unsatisfied(c,b))-old))
    def test_unsat_sentinel(self):
        c=[[s*v for s,v in zip(signs,(1,2,3))] for signs in itertools.product((-1,1),repeat=3)]
        self.assertFalse(p.solve_exact(3,c)["satisfiable"])
        for arm in ("random-local","walksat"):
            result=p.baseline(dict(n=3,clauses=c,rng_seed=77),arm,96)
            self.assertEqual(result["outcome"],"UNKNOWN")
            self.assertEqual(result["flips"],96)
    def test_baseline_trace(self):
        f=p.random_sat(8,34,random.Random(90));f["rng_seed"]=80
        for arm in ("random-local","walksat"):
            r=p.baseline(f,arm,96);a=r["initial_assignment"][:]
            for step in r["steps"]:
                self.assertIn(step["clause"],p.unsatisfied(f["clauses"],a))
                self.assertEqual(step["breaks"],[p.break_count(f["clauses"],a,v) for v in step["candidates"]])
                v=step["candidates"][step["selected"]];a[v]=not a[v]
                self.assertEqual(a,step["assignment"])
            self.assertEqual(r["solved"],p.verify_witness(f["n"],f["clauses"],a))
    def test_generated_teaching(self):
        m=p.material(2011000,per_size=1)
        for category,examples in enumerate(m["examples"]):
            self.assertEqual(len(examples),16)
            for e in examples:
                f=m["training"][e["formula_index"]]
                self.assertIn(e["clause_index"],p.unsatisfied(f["clauses"],e["assignment"]))
                b=p.break_count(f["clauses"],e["assignment"],e["variable"])
                self.assertEqual(b,e["break_count"]);self.assertEqual(min(b,3),category)
        self.assertEqual(len(m["tests"]),4)
    def test_fixed_decoder(self):
        self.assertEqual(p.choose([0,8,0],random.Random(1),noise=0),(1,False))
        with self.assertRaises(ValueError):p.validate(3,[(1,1,2)])
        self.assertFalse(p.verify_witness(3,[(1,2,3)],[1,False,False]))
if __name__=="__main__":unittest.main()

