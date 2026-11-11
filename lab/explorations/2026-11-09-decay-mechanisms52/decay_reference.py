"""Mathematical reference for proposed 5.2 laws; not a runnable ThreeMind kernel.

Each reinforcement contribution retains its own dimensionless elapsed age. All
contributions share the connection's experience-dependent decay timescale.
Queries are pure. No approximation, cohort trimming, stimuli or task outputs
are implemented here. Kernel integration and behavioral trials are separate.
"""
from dataclasses import dataclass
import math

CURVES=('exponential','inverse-logarithmic','power-law')


def finite(*values):
    return all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in values)


def remaining(curve,age):
    if not finite(age) or age<0:raise ValueError('finite nonnegative age required')
    if curve=='exponential':return math.exp(-math.log(2)*age)
    if curve=='inverse-logarithmic':
        k=math.expm1(1)
        logarithm=math.log1p(k*age) if age<1e300 else math.log(age)+math.log(k)
        return 1/(1+logarithm)
    if curve=='power-law':return 1/(1+age)
    raise ValueError('unknown curve')


def advance_age(timescale,seconds,minimum,relaxation_rate):
    if not finite(timescale,seconds,minimum,relaxation_rate) or minimum<=0 or timescale<minimum or seconds<0 or relaxation_rate<0:
        raise ValueError('invalid retention parameters')
    end=max(minimum,timescale-relaxation_rate*seconds)
    falling=min(seconds,(timescale-minimum)/relaxation_rate) if relaxation_rate else 0.
    integral=(math.log1p(relaxation_rate*falling/end)/relaxation_rate if falling else 0.)+(seconds-falling)/end
    return integral,end


def seconds_for_age(timescale,age,minimum,relaxation_rate):
    if not finite(timescale,age,minimum,relaxation_rate) or timescale<minimum or minimum<=0 or age<0 or relaxation_rate<0:
        raise ValueError('invalid inverse parameters')
    if not relaxation_rate:return timescale*age
    until_floor=math.log(timescale/minimum)/relaxation_rate
    if age<=until_floor:return timescale*-math.expm1(-relaxation_rate*age)/relaxation_rate
    return (timescale-minimum)/relaxation_rate+(age-until_floor)*minimum


@dataclass(frozen=True)
class Contribution:
    amount:float
    age:float


@dataclass(frozen=True)
class Trace:
    curve:str
    components:tuple=()

    def __post_init__(self):
        if self.curve not in CURVES:raise ValueError('invalid trace')
        previous=math.inf
        for c in self.components:
            if not finite(c.amount,c.age) or c.amount<=0 or not 0<=c.age<previous:
                raise ValueError('invalid contribution history')
            previous=c.age

    def value(self,additional_age=0.):
        if not finite(additional_age) or additional_age<0:raise ValueError('invalid additional age')
        return math.fsum(c.amount*remaining(self.curve,c.age+additional_age) for c in self.components)

    def elapse(self,additional_age):
        if not finite(additional_age) or additional_age<0:raise ValueError('cannot reverse age')
        parts=[]
        for c in self.components:
            age=c.age+additional_age
            if parts and parts[-1].age==age:
                last=parts[-1];parts[-1]=Contribution(last.amount+c.amount,age)
            else:parts.append(Contribution(c.amount,age))
        return Trace(self.curve,tuple(parts))

    def reinforce(self,amount,cap=1.):
        if not finite(amount,cap) or amount<0 or not 0<cap<=1:raise ValueError('invalid reinforcement or cap')
        accepted=min(amount,max(0.,cap-self.value()))
        if not accepted:return self
        parts=list(self.components)
        if parts and parts[-1].age==0:
            last=parts[-1];parts[-1]=Contribution(last.amount+accepted,0.)
        else:parts.append(Contribution(accepted,0.))
        return Trace(self.curve,tuple(parts))

    def scale(self,factor):
        if not finite(factor) or not 0<=factor<=1:raise ValueError('damage scale must be in [0,1]')
        if factor==0:return Trace(self.curve,())
        return Trace(self.curve,tuple(Contribution(c.amount*factor,c.age) for c in self.components if c.amount*factor>0))

    def crossing_age(self,floor,maximum_age):
        """Earliest added age reaching floor, or None within a declared horizon."""
        if not finite(floor,maximum_age) or floor<=0 or maximum_age<0:raise ValueError('invalid crossing bound')
        if self.value()<=floor:return 0.
        if self.value(maximum_age)>floor:return None
        low,high=0.,min(1.,maximum_age)
        while self.value(high)>floor:high=min(maximum_age,high*2)
        for _ in range(100):
            mid=(low+high)/2
            if self.value(mid)>floor:low=mid
            else:high=mid
        return high
