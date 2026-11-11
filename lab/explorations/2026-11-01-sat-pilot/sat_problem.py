"""Pure SAT environment, material generator and declared local-search baselines."""
from __future__ import annotations
import itertools
import random
import time

def validate(n, clauses):
    if type(n) is not int or n < 3:
        raise ValueError("at least 3 variables")
    for c in clauses:
        if len(c) != 3 or len({abs(x) for x in c}) != 3:
            raise ValueError("exactly 3 distinct variables per clause")
        if any(type(x) is not int or not 1 <= abs(x) <= n for x in c):
            raise ValueError("invalid literal")

def unsatisfied(clauses, a):
    return [i for i,c in enumerate(clauses) if not any(a[abs(x)-1] == (x>0) for x in c)]

def verify_witness(n, clauses, a):
    validate(n, clauses)
    if len(a)!=n or any(type(x) is not bool for x in a):
        return False
    bits = sum(int(x)<<i for i,x in enumerate(a))
    return all(any(bool(bits & (1<<(abs(x)-1))) == (x>0) for x in c) for c in clauses)

def break_count(clauses, a, variable):
    count=0
    for c in clauses:
        true=[x for x in c if a[abs(x)-1] == (x>0)]
        count += len(true)==1 and abs(true[0])-1==variable
    return count

def solve_exact(n, clauses):
    """DPLL used only for material preparation and reference checking."""
    validate(n, clauses); calls=0; start=time.perf_counter()
    def search(rows, values):
        nonlocal calls
        calls+=1
        while True:
            if not rows: return [values.get(i,False) for i in range(1,n+1)]
            if any(not c for c in rows): return None
            units=[c[0] for c in rows if len(c)==1]
            if not units: break
            x=units[0]
            if abs(x) in values and values[abs(x)] != (x>0): return None
            values=values|{abs(x):x>0}
            rows=[tuple(v for v in c if v != -x) for c in rows if x not in c]
        v=abs(min(rows,key=len)[0])
        for yes in (False,True):
            x=v if yes else -v
            child=[tuple(t for t in c if t != -x) for c in rows if x not in c]
            found=search(child,values|{v:yes})
            if found is not None: return found
        return None
    found=search([tuple(c) for c in clauses],{})
    return dict(witness=found,satisfiable=found is not None,recursive_calls=calls,
                wall_seconds=time.perf_counter()-start)

def random_sat(n,m,rng):
    """Uniform random 3-CNF conditioned on SAT; never plant a hidden answer."""
    for attempt in range(10000):
        rows=set()
        while len(rows)<m:
            vs=sorted(rng.sample(range(1,n+1),3))
            rows.add(tuple(v if rng.getrandbits(1) else -v for v in vs))
        rows=sorted(rows); oracle=solve_exact(n,rows)
        if oracle["satisfiable"]:
            perm=list(range(1,n+1));rng.shuffle(perm)
            rows=[[perm[abs(x)-1]*(1 if x>0 else -1) for x in c] for c in rows]
            rng.shuffle(rows)
            return dict(n=n,clauses=rows,oracle=solve_exact(n,rows),rejection_attempts=attempt+1)
    raise RuntimeError("material budget exhausted")

def material(seed, per_size=12):
    rng=random.Random(seed ^ 0x5A7C001)
    training=[random_sat(12,50,rng) for _ in range(8)]
    examples=[[] for _ in range(4)]
    for _ in range(100000):
        if all(len(x)==16 for x in examples): break
        fi=rng.randrange(len(training));f=training[fi]
        a=[bool(rng.getrandbits(1)) for _ in range(f["n"])]
        bad=unsatisfied(f["clauses"],a)
        if not bad: continue
        ci=rng.choice(bad)
        for x in f["clauses"][ci]:
            v=abs(x)-1;b=break_count(f["clauses"],a,v);cat=min(b,3)
            if len(examples[cat])<16:
                examples[cat].append(dict(formula_index=fi,assignment=a,clause_index=ci,
                                         variable=v,break_count=b))
    if not all(len(x)==16 for x in examples): raise RuntimeError("incomplete teaching coverage")
    tests=[]
    for i in range(per_size):
        for n in (12,20):
            f=random_sat(n,round(4.2*n),rng)
            f.update(id=f"n{n}-{i:02d}",kind="satisfiable",rng_seed=rng.getrandbits(63))
            tests.append(f)
    for i in range(2):
        rows=[[v*s for v,s in zip((1,2,3),signs)] for signs in itertools.product((-1,1),repeat=3)]
        rng.shuffle(rows)
        tests.append(dict(id=f"unsat-{i}",kind="unsatisfiable-sentinel",n=3,clauses=rows,
                          rng_seed=rng.getrandbits(63),oracle=solve_exact(3,rows)))
    canonical=lambda f: tuple(sorted(tuple(sorted(c)) for c in f["clauses"]))
    if set(map(canonical,training)) & set(map(canonical,tests)): raise RuntimeError("test overlap")
    return dict(seed=seed,training=training,examples=examples,tests=tests)

def begin_problem(problem):
    rng=random.Random(problem["rng_seed"])
    return [bool(rng.getrandbits(1)) for _ in range(problem["n"])],rng

def choose(scores,rng,noise=.25):
    """Fixed decoder: it receives no formula, category or answer."""
    if rng.random()<noise: return rng.randrange(len(scores)),True
    best=max(scores)
    return rng.choice([i for i,v in enumerate(scores) if abs(v-best)<=1e-12]),False

def baseline(problem,kind,limit):
    a,rng=begin_problem(problem);initial=a[:];steps=[];start=time.perf_counter()
    for step in range(limit):
        bad=unsatisfied(problem["clauses"],a)
        if not bad: break
        ci=rng.choice(bad);candidates=[abs(x)-1 for x in problem["clauses"][ci]];rng.shuffle(candidates)
        breaks=[break_count(problem["clauses"],a,v) for v in candidates]
        if kind=="walksat" and 0 in breaks:
            selected=rng.choice([i for i,b in enumerate(breaks) if b==0]);noise=False
        elif kind=="walksat": selected,noise=choose([-b for b in breaks],rng,.5)
        elif kind=="random-local": selected,noise=rng.randrange(3),True
        else: raise ValueError(kind)
        a[candidates[selected]]=not a[candidates[selected]]
        steps.append(dict(step=step,clause=ci,candidates=candidates,breaks=breaks,
                          selected=selected,noise=noise,assignment=a[:]))
    solved=verify_witness(problem["n"],problem["clauses"],a)
    return dict(initial_assignment=initial,final_assignment=a,solved=solved,
                outcome="SAT" if solved else "UNKNOWN",flips=len(steps),steps=steps,
                wall_seconds=time.perf_counter()-start)

