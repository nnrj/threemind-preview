"""Continuous /5.1 subjects; fixed port readout; no kernel modifications."""
from __future__ import annotations
import copy
import json
import random
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"lab/explorations/2026-10-16-mechanism-discovery"))
import pilot_m2 as base
from pilot_m1 import differences
from sat_problem import begin_problem,break_count,choose,unsatisfied,verify_witness
SYMBOLS=[f"C{i}" for i in range(4)]+[f"U{i}" for i in range(4)]+["P","N","Q","R","K"]
QUERY_US,READ_US,TEACH_US,LIMIT=200_000,110_000,250_000,96

class Subject:
    def __init__(self,seed,saved=None):
        self.seed=seed
        if saved is None:
            rng=random.Random(seed)
            self.mapping=dict(zip(SYMBOLS,rng.sample(range(1,2**32),len(SYMBOLS))))
            self.rng_state=json.loads(base.encoded(rng.getstate()))
            self.core=base.create_engine(base.Local51Config(seed=seed,energy_seed=seed ^ 0x1634AB),
                                         kernel_id=base.KERNEL,backend="native")
            self.next_background=0;self.branch=None;self.cursor=dict(stage="birth",completed=0)
            self.world=None;self.recent=[];self.input_digest=base.digest([]);self.input_count=0
        else:
            if seed!=saved["seed"] or saved["schema"]!="threemind.sat-subject/1":
                raise ValueError("identity mismatch")
            self.mapping=saved["mapping"];self.rng_state=saved["rng_state"]
            self.core=base.create_engine(state=base.StateImage.from_dict(saved["core"]),
                                         kernel_id=base.KERNEL,backend="native")
            for k in ("next_background","branch","cursor","world","recent","input_digest","input_count"):
                setattr(self,k,copy.deepcopy(saved[k]))
            if self.save()!=saved: raise RuntimeError("complete restore mismatch")
        if self.core.dynamics!=base.KERNEL: raise RuntimeError("wrong kernel")
    @classmethod
    def restore(cls,saved): return cls(saved["seed"],saved)
    def save(self):
        return dict(schema="threemind.sat-subject/1",seed=self.seed,core=self.core.capture_state().to_dict(),
                    mapping=self.mapping,rng_state=self.rng_state,next_background=self.next_background,
                    branch=self.branch,cursor=self.cursor,world=self.world,recent=self.recent,
                    input_digest=self.input_digest,input_count=self.input_count,
                    readout=dict(type="fixed-P-minus-N-activation/1",optimizer=None,trainable=False,
                                 read_us=READ_US,query_us=QUERY_US))
    def inject(self,t,values):
        event=dict(time_us=t,channels=[[self.mapping[k],v] for k,v in values.items()],intensity=1.)
        self.core.inject(base.Stimulus(t,tuple(tuple(x) for x in event["channels"]),1.))
        self.input_digest=base.digest([self.input_digest,event]);self.input_count+=1
        return event
    def advance(self,until):
        if until<self.core.time_us: raise ValueError("time reversal")
        while self.next_background<=until:
            self.inject(self.next_background,{"K":.2});self.next_background+=500_000
        self.core.advance_to(until)
        if self.core.life=="dead": raise RuntimeError("new death; preserve in-flight and ask")
    def query(self,category):
        if type(category) is not int or category not in range(4): raise ValueError("invalid category")
        start=self.core.time_us;event=self.inject(start,{f"C{category}":.8})
        self.advance(start+READ_US)
        nodes={n["channel"]:n for n in self.core.observation_nodes()}
        ports=[[nodes.get(self.mapping[k],{}).get(f,0.) for f in ("activation","direct","associative","inhibition")]
               for k in ("P","N")]
        result=dict(start_us=start,read_us=self.core.time_us,category=category,input=event,
                    ports=ports,score=ports[0][0]-ports[1][0])
        self.advance(start+QUERY_US);self.recent=(self.recent+[result])[-3:]
        return result
    def train(self,examples,shuffled=False):
        before=base.digest(self.save());start=time.perf_counter();events=[]
        self.advance(self.core.time_us+1_000_000)
        for r in range(16):
            preferred=r%4 if shuffled else 0
            for category in range(4):
                for prefix in ("C","U"):
                    positive=category==preferred
                    port=("P" if positive else "N") if prefix=="C" else ("Q" if positive else "R")
                    event=self.inject(self.core.time_us,{f"{prefix}{category}":.4,port:.4})
                    self.advance(self.core.time_us+TEACH_US)
                    nodes={n["channel"]:n for n in self.core.observation_nodes()}
                    activity=[nodes.get(self.mapping[s],{}).get("activation",0.) for s in (f"{prefix}{category}",port)]
                    events.append(dict(example=examples[category][r],prefix=prefix,category=category,
                                       teacher_preference=positive,stimulus=event,teaching_activity=activity))
        self.advance(self.core.time_us+1_000_000)
        self.cursor=dict(stage="trained-shuffled" if shuffled else "trained",completed=128)
        return dict(before_sha256=before,after_sha256=base.digest(self.save()),events=events,
                    wall_seconds=time.perf_counter()-start)
    def solve(self,problem,limit=LIMIT):
        before=base.digest(self.save());start_us=self.core.time_us;start=time.perf_counter()
        a,rng=begin_problem(problem);initial=a[:];steps=[]
        self.world=dict(problem_id=problem["id"],assignment=a[:],step=0,
                        environment_rng=json.loads(base.encoded(rng.getstate())))
        for step in range(limit):
            bad=unsatisfied(problem["clauses"],a)
            if not bad: break
            ci=rng.choice(bad);candidates=[abs(x)-1 for x in problem["clauses"][ci]];rng.shuffle(candidates)
            breaks=[break_count(problem["clauses"],a,v) for v in candidates]
            reads=[self.query(min(b,3)) for b in breaks]
            selected,noise=choose([r["score"] for r in reads],rng)
            a[candidates[selected]]=not a[candidates[selected]]
            steps.append(dict(step=step,clause=ci,candidates=candidates,breaks=breaks,
                              queries=reads,selected=selected,noise=noise,assignment=a[:]))
            self.world=dict(problem_id=problem["id"],assignment=a[:],step=step+1,
                            environment_rng=json.loads(base.encoded(rng.getstate())))
        solved=verify_witness(problem["n"],problem["clauses"],a)
        self.cursor=dict(stage="test",completed_tests=self.cursor.get("completed_tests",0)+1,problem_id=problem["id"])
        return dict(initial_assignment=initial,final_assignment=a,solved=solved,outcome="SAT" if solved else "UNKNOWN",
                    flips=len(steps),steps=steps,start_us=start_us,end_us=self.core.time_us,
                    before_sha256=before,after_sha256=base.digest(self.save()),wall_seconds=time.perf_counter()-start)

def select_edges(subject,teaching):
    graph=subject.core.graph();nodes={n["channel"]:n for n in graph["nodes"]}
    pairs={(e["source"],e["target"]):e for e in graph["edges"]};groups={}
    for group,prefix,ports in [("target","C",("P","N")),("matched","U",("Q","R"))]:
        rows=[]
        for category in range(4):
            src=nodes[subject.mapping[f"{prefix}{category}"]]["id"]
            dst=nodes[subject.mapping[ports[int(category!=0)]]]["id"]
            edge=pairs.get((src,dst))
            acts=[e["teaching_activity"] for e in teaching["events"] if e["prefix"]==prefix and e["category"]==category]
            if edge:
                rows.append(dict(edge=[src,dst],category=category,weight=edge["weight"],
                                 teaching_activity=[sum(x[i] for x in acts)/len(acts) for i in (0,1)],
                                 degrees=[[sum(e["source"]==x for e in graph["edges"]),
                                           sum(e["target"]==x for e in graph["edges"])] for x in (src,dst)]))
        groups[group]=rows
    a,b=groups["target"],groups["matched"]
    residuals=dict(counts=[len(a),len(b)],maximum_weight_difference=max([abs(x["weight"]-y["weight"]) for x,y in zip(a,b)],default=1.),
                   degrees_equal=all(x["degrees"]==y["degrees"] for x,y in zip(a,b)),
                   maximum_activity_difference=max([abs(x["teaching_activity"][i]-y["teaching_activity"][i])
                                                    for x,y in zip(a,b) for i in (0,1)],default=1.))
    valid=(len(a)==len(b)==4 and residuals["degrees_equal"]
           and residuals["maximum_weight_difference"]<=.05 and residuals["maximum_activity_difference"]<=.05)
    return dict(groups=groups,residuals=residuals,valid=valid)

def causal_child(parent,selection,arm):
    child=Subject.restore(parent);before=child.save()
    edges=[x["edge"] for x in selection["groups"]["matched" if arm=="matched" else "target"]]
    if arm!="intact": child.core.intervene(edges=[] if arm=="sham" else edges,action="silence")
    masked=child.save()
    if arm=="restored": child.core.intervene(edges=edges,action="restore")
    after=child.save();changed=differences(before,masked)
    if any(x!="core.silenced_edges" for x in changed): raise RuntimeError("non-mask field changed")
    if arm=="restored" and base.digest(before)!=base.digest(after): raise RuntimeError("inexact reversal")
    child.branch=dict(parent_sha256=base.digest(parent),arm=arm,parent_time_us=child.core.time_us)
    return child,dict(arm=arm,edges=edges if arm not in ("intact","sham") else [],
                      changed_fields=changed,before_sha256=base.digest(before),
                      masked_sha256=base.digest(masked),restored_sha256=base.digest(after))

