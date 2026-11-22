"""Serial, restartable ocean observations. Each closed segment has its complete world."""
from __future__ import annotations

from contextlib import ExitStack
import gzip
import json
import os
import shutil
import time
from zipfile import ZipFile, ZIP_DEFLATED

from apparatus import ROOT, HERE, KERNEL, GIB, StateImage, Primitive63, Contact63, Enclosure63, read, sha
from registration import BATCH, directory, pool, exclusive_json
from lab.tools.ocean_evolution_cli import RecordWriter
from threemind_lab.storage_files import atomic_json
import sys
sys.path.insert(0,str(ROOT/"lab/explorations/2026-10-13-eye-hand-shape-color"))
from host_resource_guard import check_resources, Limits

SECOND = 1_000_000
SEGMENT = 60*SECOND


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False).encode("utf8")


def snapshot(w, path):
    context = w.capture()
    partial = path.with_suffix(".partial")
    with ZipFile(partial, "x", ZIP_DEFLATED, compresslevel=2, allowZip64=True) as z:
        z.writestr("world.json", encoded({"context":context, "protocol":w.p.model_dump(by_alias=True),
                                          "kind":type(w).__name__, "time_us":w.time_us}))
        for i, engine in w.engines.items():
            if engine.dynamics != KERNEL:
                raise RuntimeError("non-6.3 individual in complete world")
            z.writestr(f"cores/{i}.json", engine.capture_state().payload)
    partial.rename(path)


def restore(path):
    with ZipFile(path) as z:
        w = json.loads(z.read("world.json"))
        images = {int(n[6:-5]):StateImage(z.read(n)) for n in z.namelist() if n.startswith("cores/")}
    classes = {k.__name__:k for k in (Primitive63,Contact63,Enclosure63)}
    if w["kind"] == "Carrion63":
        from carrion import Carrion63
        classes["Carrion63"] = Carrion63
    world = classes[w["kind"]](w["protocol"],state=w["context"],images=images)
    # JSON stringifies individual IDs used as dict keys. Normalize them before sorting
    # (numeric order 2,10 and string order "10","2" serialize differently).
    if encoded(json.loads(encoded(world.capture()))) != encoded(w["context"]):
        raise RuntimeError(f"restored whole world differs at {path}")
    return world


def footprint(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def guard(code, work):
    if (work/"STOP").exists() or (work.parent/"STOP").exists():
        raise RuntimeError("operator STOP")
    store = pool()
    expected = store.guard(BATCH,"study-"+code.lower(),check_directory=False)
    if work != expected:
        raise RuntimeError("data volume path changed")
    check_resources(work, limits=Limits(commit_gib=5, ram_gib=4, system_disk_gib=5, data_disk_gib=5))
    if shutil.disk_usage("E:/").free < 15*GIB:
        raise RuntimeError("E: free space below authorized study floor")


def extinct(w):
    if type(w) is Primitive63:
        return all(e.life == "dead" for e in w.engines.values())
    return not any(b.physical for b in w.bodies.values())


def checked_metrics(w):
    m = w.metrics()
    if abs(m["energy_balance_error"]) > max(1e-4,w.totals["environment_food"]*1e-8):
        raise RuntimeError(f"water-world energy ledger differs by {m['energy_balance_error']}")
    if any(e.dynamics != KERNEL for e in w.engines.values()):
        raise RuntimeError("unexpected kernel identity")
    return m


def file_lines(stream, value):
    stream.write(encoded(value)+b"\n")


def observe(w, folder, target, *, code=None, work=None, stop_event=None):
    """Advance only by prescribed water-world ticks. Preserve inputs and decisions, including zeros."""
    folder.mkdir()
    writer = RecordWriter(folder/"inputs",chunk_steps=100)
    live_ticks = 0
    clock = time.monotonic()
    last_guard, last_status = clock-2, clock-32
    stop = None
    reason = "boundary"
    start = w.time_us
    with ExitStack() as stack:
        trace, activity, events = [stack.enter_context(gzip.open(folder/(n+".jsonl.gz"),"wb",compresslevel=2))
                                   for n in ("trajectory","activity","events")]
        while w.time_us < target:
            now = time.monotonic()
            if code and now-last_guard >= 1:
                try:
                    guard(code,work)
                except (RuntimeError,OSError,ValueError) as exc:
                    reason,stop = "paused",str(exc)
                    break
                last_guard = now
            if code and now-last_status >= 30:
                atomic_json(work/"progress.json",dict(case=folder.parent.name,simulated_us=w.time_us,
                    segment_started_us=start,segment_target_us=target,alive=sum(b.physical for b in w.bodies.values()),
                    grains=sum(b.grains for b in w.bodies.values()),births=w.totals["births"],
                    elapsed_wall_s=round(now-clock,2),epoch=time.time(),pid=os.getpid()))
                last_status = now
            if w.time_us % SECOND == 0:
                m = checked_metrics(w)
                file_lines(trace, dict(time_us=w.time_us, food_ids=w.food_ids,food_positions=w.food.tolist(),
                                       **{k:m[k] for k in ("members","totals","energy_balance_error")}))
                rows = []
                for i in sorted(i for i,b in w.bodies.items() if b.physical)[:4]:
                    nodes = w.engines[i].observation_nodes()
                    if any(int(n["id"]) != int(n["channel"]) for n in nodes):
                        raise RuntimeError("sensor-to-node identity is not stable")
                    rows.append(dict(individual=i,nodes=[{k:n[k] for k in ("id","channel","activation","inhibition")} for n in nodes]))
                file_lines(activity,dict(time_us=w.time_us,members=rows))
            row_events = w.step(writer.record)
            for ev in row_events:
                file_lines(events,ev)
            live_ticks += sum(b.physical for b in w.bodies.values())
            if stop_event and stop_event(w,row_events):
                reason = "qualified_parent"
                break
            if extinct(w):
                reason = "extinct"
                break
        writer.flush()
    m = checked_metrics(w)
    snapshot(w, folder/"end.zip")
    exclusive_json(folder/"segment.json",dict(start_us=start,end_us=w.time_us,live_ticks=live_ticks,
        reason=reason,pause=stop,wall_s=time.monotonic()-clock,snapshot_sha256=sha(folder/"end.zip"),
        grains=sum(b.grains for b in w.bodies.values()),births=w.totals["births"],
        predations=w.totals["predations"],energy_error=m["energy_balance_error"]))
    return reason,stop


def run_case(code, key, factory, horizon_s, *, stop_event=None, milestones=()):
    """A complete state from this case is the only admissible restart position."""
    work = directory(code)
    if not (work/"registration.json").is_file():
        raise RuntimeError("a research registration receipt is required")
    run = work/"cases"/key
    run.mkdir(parents=True,exist_ok=True)
    if (run/"result.json").exists():
        return read(run/"result.json")
    guard(code,work)
    segment_dirs = sorted(d for d in run.glob("seg-*") if d.is_dir())
    if any(not (d/"segment.json").is_file() for d in segment_dirs):
        raise RuntimeError(f"unfinished segment retained; inspect its worker and evidence: {key}")
    initial = run/"initial.zip"
    if not initial.exists():
        if segment_dirs:
            raise RuntimeError("missing initial world")
        w = factory()
        snapshot(w,initial)
    latest = segment_dirs[-1]/"end.zip" if segment_dirs else initial
    if segment_dirs and sha(latest) != read(segment_dirs[-1]/"segment.json")["snapshot_sha256"]:
        raise RuntimeError("checkpoint digest mismatch")
    w = restore(latest)
    live_ticks = sum(read(d/"segment.json")["live_ticks"] for d in segment_dirs)
    reason = read(segment_dirs[-1]/"segment.json")["reason"] if segment_dirs else "boundary"
    milestones = sorted(set([round(v*SECOND) for v in milestones]+[round(horizon_s*SECOND)]))
    while w.time_us < horizon_s*SECOND and reason not in ("qualified_parent","extinct"):
        if extinct(w):
            reason = "extinct"
            break
        target = min(w.time_us+SEGMENT, next(v for v in milestones if v>w.time_us))
        segment = run/f"seg-{len(segment_dirs):04d}"
        pool().guard(BATCH,"study-"+code.lower(),extra_bytes=64*2**20)
        reason, stop = observe(w,segment,target,code=code,work=work,stop_event=stop_event)
        live_ticks += read(segment/"segment.json")["live_ticks"]
        latest = segment/"end.zip"
        segment_dirs.append(segment)
        if stop:
            raise RuntimeError(f"{key} paused at complete state {w.time_us}: {stop}")
    m = checked_metrics(w)
    result = dict(case=key,kernel=KERNEL,horizon_s=horizon_s,reason=reason if reason!="boundary" else "horizon",
        time_us=w.time_us,end_snapshot=latest.relative_to(work).as_posix(),living_body_seconds=live_ticks*w.p.period_us/SECOND,
        grains=sum(b.grains for b in w.bodies.values()),alive=sum(b.physical for b in w.bodies.values()),
        members=m["members"],totals=m["totals"],energy_balance_error=m["energy_balance_error"],groups=m.get("groups"))
    # Verify the actual end archive before claiming the observation finished.
    restored = restore(latest)
    if encoded(restored.capture()) != encoded(w.capture()):
        raise RuntimeError("final state archive differs from the observed individual")
    exclusive_json(run/"result.json",result)
    print(key,result["reason"],w.time_us,result["grains"],result["alive"],flush=True)
    return result
