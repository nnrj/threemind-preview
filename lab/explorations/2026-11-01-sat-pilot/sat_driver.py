"""Registered SAT pilot commands. No old host, kernel, or subject is modified."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID,uuid5
import psutil
from sat_subject import Subject,base,ROOT,LIMIT,causal_child,select_edges
import sat_problem as sat
HERE=Path(__file__).resolve().parent
WORK=Path("E:/ThreeMindData/experiments/2026-11-01-sat-pilot/v1")
NS=UUID("0a6cb3e8-b53f-4f75-8486-f07c73d1f1f9")
ARMS=("intact","sham","target","matched","restored","shuffled","random-local","walksat")
def ident(key): return uuid5(NS,key)
def connection():
    base.load_env()
    # Ephemeral use of the already configured account, with no credential export.
    return base.OperationsClient(username=os.environ.get("THREEMIND_API_USERNAME"),
                                 password=os.environ.get("THREEMIND_API_PASSWORD"),
                                 token=os.environ.get("THREEMIND_API_TOKEN"),
                                 reuse_session=False,require_auth=True,source="ai")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(gzip.decompress(Path(p).read_bytes())) if str(p).endswith(".gz") else base.read(p)
def save(p,v): return base.original(p,v,compressed=str(p).endswith(".gz"))
def state(work,**kw): base.atomic_json(work/"status.json",kw)
def manifest():
    files=list(HERE.glob("*.py"))+[HERE/"protocol.zh.md",HERE/"protocol.en.md",
          ROOT/"lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py",
          ROOT/"lab/explorations/2026-10-16-mechanism-discovery/pilot_m1.py",
          ROOT/"lab/tools/study_lock.py",
          ROOT/"lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py"]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
def check_frozen(work):
    for rel,digest in load(work/"runner-manifest.json").items():
        if sha(ROOT/rel)!=digest: raise RuntimeError("frozen file changed: "+rel)
    recorded=load(work/"implementation.json")
    current=base.capture_implementation("native")
    # Compare actual kernel and installed module hashes; Git HEAD itself may advance.
    if recorded != current:
        raise RuntimeError("kernel, installed implementation or dependencies changed")
def recorder(work,c):
    p=load(work/"platform.json");r=base.ResearchRecorder(work,p["project_id"],client=c)
    r.resume_recording();return r
def resources(work):
    report=base.resource_check(work)
    if report["available_bytes"]["commit"] < 7*2**30:
        raise RuntimeError("start requires 5GiB reserve plus 2GiB startup margin")
    if report["available_bytes"]["data_disk"] < 27*2**30:
        raise RuntimeError("insufficient original/archive/readback allowance")
    return report
def original_size(work):
    return sum(p.stat().st_size for p in work.rglob("*") if p.is_file() and "readback" not in p.parts)
def boundary(work):
    if (work/"STOP").exists(): raise InterruptedError("STOP at complete boundary")
    base.resource_check(work)
    if original_size(work)>512*2**20: raise InterruptedError("512MiB original budget")
def prepare(work):
    if (work/"platform.json").exists(): raise RuntimeError("already registered; inspect status")
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        resources(work)
        name="2026-11-01 ThreeMind · 3-SAT 局部选择策略探索 v1"
        matches=[p for p in c.call("projects.list",{}) if p["name"]==name]
        if len(matches)>1: raise RuntimeError("ambiguous project")
        project=matches[0] if matches else c.request("POST","/api/v2/projects",body={"name":name})
        save(work/"platform.json",dict(project_id=project["id"],resource_id="sat-pilot-20261101-v1"))
        r=base.ResearchRecorder(work,project["id"],client=c)
        r.register(dict(source_key="sat-pilot:20261101:v1",title=name,classification="development",
                        execution_status="running",executor="ai",kernels=[base.KERNEL],
                        protocol=(HERE/"protocol.zh.md").read_text(encoding="utf-8-sig"),
                        protocol_version=base.digest(manifest()),required_roles=["protocol","report","note"],
                        metadata=dict(work=str(work),independent_origins=8,scope="learned local heuristic; not P=NP",
                                      authorization="2026-11-01 explicit design and execute request")),
                   request_id=ident("register"))
        r.synchronize(strict=True)
        c.request("POST","/api/v2/storage/resources",body=dict(resource_id="sat-pilot-20261101-v1",
                  target_id="managed-research-experiments",relative_path="2026-11-01-sat-pilot/v1",
                  registered_work_path=str(work),writer_mode="cooperative",expected_revision=0),
                  headers={"X-ThreeMind-Request-ID":str(ident("resource"))})
        c.request("POST","/api/v2/storage/record-evidence-grants",body=dict(project_id=project["id"],resource_id="sat-pilot-20261101-v1"),
                  headers={"X-ThreeMind-Request-ID":str(ident("grant"))})
        save(work/"implementation.json",base.capture_implementation("native"))
        frozen=manifest();save(work/"runner-manifest.json",frozen)
        for rel in frozen: r.save_original("frozen/"+rel,(ROOT/rel).read_bytes())
        for o in range(8): save(work/f"material/o{o}.json",sat.material(2011100+o))
        save(work/"material/apparatus.json",sat.material(2011000,per_size=1))
        for lang in ("zh","en"):
            r.text(dict(request_id=str(ident("protocol-"+lang)),identity=str(ident("protocol-doc-"+lang)),
                        expected_revision=0,kind="protocol",title="3-SAT pilot protocol "+lang,
                        markdown=(HERE/f"protocol.{lang}.md").read_text(encoding="utf-8-sig")))
        r.synchronize(strict=True)
        state(work,state="registered-awaiting-apparatus",record=r.experiment,origins_completed=0)
        print(json.dumps(dict(record=r.experiment,project=project["id"],pending=r.status["pending"])))
def mark(work,unit):
    save(work/"in-flight.json",dict(unit=unit,epoch=time.time(),pid=os.getpid(),created_at=psutil.Process().create_time()))
def clear(work): (work/"in-flight.json").unlink()
def apparatus(work):
    with base.worker_lock(work):
        check_frozen(work);resources(work)
        if (work/"apparatus.json").exists() or (work/"in-flight.json").exists():
            raise RuntimeError("apparatus exists or incomplete; do not repeat")
        mark(work,"apparatus")
        with base.Guard(work) as guard:
            m=load(work/"material/apparatus.json");s=Subject(2011000)
            save(work/"apparatus/birth.json.gz",s.save())
            teaching=s.train(m["examples"]);parent=s.save()
            save(work/"apparatus/parent.json.gz",parent);save(work/"apparatus/teaching.json.gz",teaching)
            selection=select_edges(s,teaching);save(work/"apparatus/selection.json",selection)
            before=base.digest(s.save())
            for _ in range(5): s.core.graph();s.core.metrics();s.core.observation_nodes();s.save()
            passive=before==base.digest(s.save())
            restored=Subject.restore(parent)
            a=[s.query(x) for x in (2,0,3,1)]
            b=[restored.query(x) for x in (2,0,3,1)]
            continuity=a==b and base.digest(s.save())==base.digest(restored.save())
            save(work/"apparatus/continuity.json.gz",dict(first=a,second=b,state_a=s.save(),state_b=restored.save()))
            children={}
            for arm in ("intact","sham","target","matched","restored"):
                child,receipt=causal_child(parent,selection,arm)
                result=child.solve(m["tests"][0],limit=4)
                save(work/f"apparatus/{arm}.json.gz",dict(receipt=receipt,result=result,state=child.save()))
                children[arm]=result["steps"]
            equality=children["intact"]==children["sham"]==children["restored"]
            result=dict(passive_observation=passive,whole_restore=continuity,reversal_and_sham=equality,
                        matching=selection["valid"],seed=2011000,
                        passed=passive and continuity and equality,matching_residuals=selection["residuals"],
                        policy_probe=[dict(category=x["category"],score=x["score"]) for x in a])
            if not result["passed"]: raise RuntimeError("apparatus failed; preserve marker")
            save(work/"apparatus.json",result);clear(work)
            state(work,state="apparatus-passed-awaiting-review",origins_completed=0)
            print(json.dumps(result))
def current_subject(folder):
    row=load(folder/"current.json");path=folder/row["file"]
    if sha(path)!=row["sha256"]: raise RuntimeError("current state hash mismatch")
    return Subject.restore(load(path)),row
def commit(folder,s,name,completed):
    receipt=save(folder/name,s.save())
    base.atomic_json(folder/"current.json",dict(file=name,completed=completed,time_us=s.core.time_us,**receipt))
def run(work):
    with base.worker_lock(work):
        check_frozen(work);resources(work)
        if (work/"in-flight.json").exists() or (work/"STOP").exists(): raise RuntimeError("unresolved marker")
        if not load(work/"apparatus.json")["passed"]: raise RuntimeError("apparatus not passed")
        review=load(work/"apparatus-review.json")
        if not review.get("approved") or review["apparatus_sha256"]!=sha(work/"apparatus.json"):
            raise RuntimeError("review missing/stale")
        if load(work/"status.json")["state"] in ("awaiting-analysis","completed"): raise RuntimeError("already computed")
        base.atomic_json(work/"host.json",dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=sys.argv))
        try:
            with base.Guard(work) as guard:
                for o in range(8):
                    folder=work/f"origins/o{o}";folder.mkdir(parents=True,exist_ok=True)
                    if (folder/"done.json").exists(): continue
                    m=load(work/f"material/o{o}.json")
                    birth=folder/"birth.json.gz"
                    if not birth.exists(): save(birth,Subject(2011100+o).save())
                    for history in ("trained","shuffled"):
                        parent=folder/f"{history}.json.gz"
                        if not parent.exists():
                            boundary(work);mark(work,f"o{o}/{history}")
                            s=Subject.restore(load(birth));s.branch=dict(parent_sha256=base.digest(load(birth)),history=history)
                            teaching=s.train(m["examples"],shuffled=history=="shuffled")
                            save(folder/f"{history}-teaching.json.gz",teaching);save(parent,s.save());clear(work)
                    if not (folder/"selection.json").exists():
                        s=Subject.restore(load(folder/"trained.json.gz"))
                        save(folder/"selection.json",select_edges(s,load(folder/"trained-teaching.json.gz")))
                    selection=load(folder/"selection.json")
                    for arm in ARMS:
                        af=folder/arm;af.mkdir(exist_ok=True)
                        if (af/"done.json").exists(): continue
                        s=None;completed=0
                        if arm not in ("walksat","random-local"):
                            if (af/"current.json").exists(): s,row=current_subject(af);completed=row["completed"]
                            else:
                                if arm=="shuffled":
                                    s=Subject.restore(load(folder/"shuffled.json.gz"))
                                    receipt=dict(history="shuffled",parent_sha256=base.digest(s.save()))
                                else: s,receipt=causal_child(load(folder/"trained.json.gz"),selection,arm)
                                save(af/"lineage.json",receipt);commit(af,s,"whole-000.json.gz",0)
                        else:
                            completed=len(list(af.glob("result-*.json.gz")))
                        for i in range(completed,len(m["tests"])):
                            boundary(work);p=m["tests"][i]
                            mark(work,f"o{o}/{arm}/test-{i}")
                            result=s.solve(p) if s else sat.baseline(p,arm,LIMIT)
                            result.update(problem_id=p["id"],kind=p["kind"],n=p["n"],arm=arm,origin=o)
                            save(af/f"result-{i:03d}.json.gz",result)
                            if s: commit(af,s,f"whole-{i+1:03d}.json.gz",i+1)
                            clear(work)
                            state(work,state="running",origin=o,arm=arm,tests_completed=i+1,origins_completed=o)
                        save(af/"done.json",dict(tests=len(m["tests"])))
                    save(folder/"done.json",dict(origin=o,arms=list(ARMS)))
                    state(work,state="running",origins_completed=o+1)
                    print(json.dumps(dict(origin=o,complete=True)),flush=True)
            state(work,state="awaiting-analysis",origins_completed=8)
        except InterruptedError as exc:
            if not (work/"STOP").exists(): save(work/"STOP",dict(reason=str(exc),epoch=time.time()))
            state(work,state="paused-complete-boundary",reason=str(exc))
            print(str(exc),flush=True)
        except Exception as exc:
            state(work,state="failed-preserve-in-flight",error=type(exc).__name__+": "+str(exc))
            raise
def status(work):
    report=dict(resources=base.resource_check(work),work=str(work))
    for name in ("status.json","host.json","apparatus.json","STOP","in-flight.json"):
        if (work/name).exists(): report[name]=load(work/name)
    if "host.json" in report:
        h=report["host.json"]
        report["host_alive"]=psutil.pid_exists(h["pid"]) and abs(psutil.Process(h["pid"]).create_time()-h["created_at"])<.01
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","apparatus","run","status"))
    p.add_argument("--work",type=Path,default=WORK);a=p.parse_args()
    globals()[a.command](a.work.resolve())

