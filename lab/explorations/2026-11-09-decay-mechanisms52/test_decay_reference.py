"""Analytical checks only; no experimental subject or production Core loaded."""
import math
import unittest
from threemind_kernels.decay52 import CURVES, Contribution, Trace, advance_age, remaining, seconds_for_age


class ReferenceTests(unittest.TestCase):
    def test_half_value_normalization_and_monotonicity(self):
        for curve in CURVES:
            self.assertEqual(remaining(curve,0),1)
            self.assertAlmostEqual(remaining(curve,1),.5)
            values=[remaining(curve,t) for t in (0,.1,1,10,100,1000)]
            self.assertEqual(values,sorted(values,reverse=True))
            self.assertTrue(all(0<=v<=1 for v in values))

    def test_partition_invariance_across_relaxation_floor(self):
        for curve in CURVES:
            for rate in (0,.0125,.125):
                for initial in (30.,31.,300.):
                    trace=Trace(curve).reinforce(.4);h=initial
                    age,end=advance_age(h,3100,30,rate);expected=trace.elapse(age)
                    for parts in (1,2,10,100):
                        s=trace;h=initial
                        for _ in range(parts):
                            a,h=advance_age(h,3100/parts,30,rate);s=s.elapse(a)
                        self.assertAlmostEqual(s.value(),expected.value(),places=12)
                        self.assertAlmostEqual(h,end,places=9)

    def test_reinforcement_keeps_old_contribution_age(self):
        for curve in CURVES:
            old=Trace(curve).reinforce(.25).elapse(2)
            new=old.reinforce(.1)
            self.assertAlmostEqual(new.value(),old.value()+.1)
            self.assertEqual(new.components[0],old.components[0])
            self.assertAlmostEqual(new.elapse(3).value(),.25*remaining(curve,5)+.1*remaining(curve,3))

    def test_queries_are_pure_and_damage_is_proportional(self):
        for curve in CURVES:
            trace=Trace(curve).reinforce(.4).elapse(.2).reinforce(.1);saved=repr(trace)
            trace.value();trace.value(100);trace.crossing_age(.008,100000)
            self.assertEqual(repr(trace),saved)
            self.assertAlmostEqual(trace.scale(.8).value(),trace.value()*.8)

    def test_cap_does_not_refresh_previous_contributions(self):
        for curve in CURVES:
            trace=Trace(curve).reinforce(.9).elapse(.2);new=trace.reinforce(1.)
            self.assertAlmostEqual(new.value(),1.)
            self.assertEqual(new.components[0],trace.components[0])

    def test_inverse_clock(self):
        for rate in (0,.0125,.125):
            for h in (30,31,300):
                for seconds in (.01,30,300,3000):
                    a,_=advance_age(h,seconds,30,rate)
                    self.assertAlmostEqual(seconds_for_age(h,a,30,rate),seconds,places=8)

    def test_crossings_and_extremely_long_inverse_log_tail(self):
        for curve in CURVES:
            trace=Trace(curve).reinforce(.025)
            a=trace.crossing_age(.008,100000)
            self.assertIsNotNone(a)
            self.assertAlmostEqual(trace.value(a),.008,places=14)
        self.assertAlmostEqual(Trace('exponential').reinforce(1).crossing_age(.008,100000),math.log2(125),places=12)
        self.assertIsNone(Trace('inverse-logarithmic').reinforce(1).crossing_age(.008,1e30))

    def test_rejects_nonfinite_parameters_and_inconsistent_history(self):
        for bad in (float('nan'),float('inf'),-1,True):
            with self.assertRaises(ValueError):remaining('exponential',bad)
            with self.assertRaises(ValueError):Trace('power-law').reinforce(bad)
            with self.assertRaises(ValueError):advance_age(30,bad,30,.125)
        for entries in ((Contribution(.1,-2),),(Contribution(-.1,0),),
                        (Contribution(.1,0),Contribution(.2,0))):
            with self.assertRaises(ValueError):Trace('power-law',entries)
        self.assertEqual(Trace('power-law').reinforce(.4).scale(0).value(),0)

    def test_short_step_keeps_positive_age_at_large_timescale(self):
        age,end=advance_age(2592000,1e-6,30,.125)
        self.assertGreater(age,0)
        self.assertAlmostEqual(age/(1e-6/2592000),1,places=12)

    def test_recent_learning_still_ages_after_extremely_long_history(self):
        for curve in CURVES:
            old=Trace(curve).reinforce(.25).elapse(1e18)
            new=old.reinforce(.1)
            expected=old.value(1)+.05
            self.assertAlmostEqual(new.value(1),expected,places=14)
            self.assertAlmostEqual(new.elapse(1).value(),expected,places=14)
            self.assertEqual(new.elapse(1).components[-1].age,1)
        self.assertGreater(remaining('inverse-logarithmic',1e308),0)


if __name__=='__main__':unittest.main()
