"""Scoped engineering acceleration with identical scalar arithmetic.

No approximation, changed decay curve, rounded age, or discarded contribution.
This is an explicit study implementation option, not a production default.
"""
from contextlib import contextmanager
import math
from threemind_kernels.decay52 import Trace,finite

ORIGINAL_VALUE=Trace.value
ORIGINAL_CROSSING=Trace.crossing_age


def value(self,additional_age=0.0):
    if not finite(additional_age) or additional_age<0:
        raise ValueError('invalid additional age')
    if self.curve=='exponential':return ORIGINAL_VALUE(self,additional_age)
    curve=self.curve
    k=math.expm1(1)
    def terms():
        for c in self.components:
            age=c.age+additional_age
            # The same checks as remaining(), fused into its scalar evaluation.
            if not isinstance(age,(int,float)) or isinstance(age,bool) or not math.isfinite(age) or age<0:
                raise ValueError('finite nonnegative age required')
            if curve=='power-law':remaining=1/(1+age)
            elif curve=='inverse-logarithmic':
                logarithm=math.log1p(k*age) if age<1e300 else math.log(age)+math.log(k)
                remaining=1/(1+logarithm)
            else:raise ValueError('unknown curve')
            yield c.amount*remaining
    return math.fsum(terms())


def crossing_age(self,floor,maximum_age):
    if not finite(floor,maximum_age) or floor<=0 or maximum_age<0:
        raise ValueError('invalid crossing bound')
    if self.value()<=floor:return 0.0
    if self.value(maximum_age)>floor:return None
    low,high=0.0,min(1.0,maximum_age)
    while self.value(high)>floor:high=min(maximum_age,high*2)
    for _ in range(100):
        mid=(low+high)/2
        # Once the midpoint equals an endpoint, the deterministic old update
        # leaves that same endpoint unchanged for every remaining iteration.
        if mid==low or mid==high:break
        if self.value(mid)>floor:low=mid
        else:high=mid
    return high


@contextmanager
def accelerated():
    assert Trace.value is ORIGINAL_VALUE and Trace.crossing_age is ORIGINAL_CROSSING
    Trace.value,Trace.crossing_age=value,crossing_age
    try:yield
    finally:Trace.value,Trace.crossing_age=ORIGINAL_VALUE,ORIGINAL_CROSSING
