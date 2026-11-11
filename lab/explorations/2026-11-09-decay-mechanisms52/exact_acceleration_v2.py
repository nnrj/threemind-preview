"""Exact power-law term evaluation using existing NumPy, with math.fsum order.

Only immutable, validated binary64 contributions use the array path. Integer,
custom or overflow cases retain the scalar path. Derived arrays are not state.
"""
from contextlib import contextmanager
import math
import numpy as np
from threemind_kernels.decay52 import Trace,Contribution,finite
from exact_acceleration import value as scalar_value,crossing_age,ORIGINAL_VALUE,ORIGINAL_CROSSING


def value(self,additional_age=0.0):
    if self.curve!='power-law' or type(additional_age) is not float:
        return scalar_value(self,additional_age)
    if not finite(additional_age) or additional_age<0:
        raise ValueError('invalid additional age')
    if not self.components:return 0.0
    cached=getattr(self,'_exact_float_arrays',None)
    if cached is None:
        if type(self.components) is not tuple or any(type(c) is not Contribution or
            type(c.amount) is not float or type(c.age) is not float for c in self.components):
            return scalar_value(self,additional_age)
        amounts=np.array([c.amount for c in self.components],dtype=np.float64)
        ages=np.array([c.age for c in self.components],dtype=np.float64)
        amounts.flags.writeable=False;ages.flags.writeable=False
        cached=(amounts,ages)
        object.__setattr__(self,'_exact_float_arrays',cached)
    if not math.isfinite(self.components[0].age+additional_age):
        return scalar_value(self,additional_age)
    amounts,ages=cached
    with np.errstate(all='ignore'):
        # Same three rounded operations as amount * (1 / (1 + (age + delta))).
        # fsum consumes terms in exactly the original contribution order.
        terms=amounts*(1.0/(1.0+(ages+additional_age)))
    return math.fsum(terms)


@contextmanager
def accelerated():
    assert Trace.value is ORIGINAL_VALUE and Trace.crossing_age is ORIGINAL_CROSSING
    Trace.value,Trace.crossing_age=value,crossing_age
    try:yield
    finally:Trace.value,Trace.crossing_age=ORIGINAL_VALUE,ORIGINAL_CROSSING
