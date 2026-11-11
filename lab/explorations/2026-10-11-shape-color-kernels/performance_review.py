"""Read preserved /4 measurements without creating or advancing an engine."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024**2):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--preflight',type=Path,required=True)
    args=p.parse_args();work=args.work.resolve()
    preflight=read(args.preflight)
    pause=read(work/'host-pause-20261011T2008.json')
    checkpoint=work/pause['checkpoint'];path=checkpoint/'system.json.gz'
    # Deserialize only. Do not import a kernel, recreate a subject or run a trial.
    with gzip.open(path,'rt',encoding='utf-8') as f:saved=json.load(f)
    core=saved['session']['core'];n=len(core['nodes']);edges=len(core['edges'])
    partial=dict(source=path.relative_to(work).as_posix(),sha256=sha(path),
        time_s=int(core['time_us'])/1e6,nodes=n,edges=edges,directed_density=edges/(n*(n-1)),
        node_visits=core['audit']['node_visits'],edge_visits=core['audit']['edge_visits'],
        expiry_checks=core['audit']['expiry_checks'],scan_visits=core['audit']['scan_visits'],
        core_advance_s=pause['checkpoint_progress']['timing']['core_ns']/1e9,
        pending_events=len(core['queue']),pending_timers=len(core['timers']),
        checkpoint_lesson=pause['checkpoint_lesson'],persisted_lesson_clips=pause['persisted_lesson_clips'])
    partial['core_seconds_per_sim_second']=partial['core_advance_s']/partial['time_s']
    rows={}
    for arm,case in preflight['kernels'].items():
        m=case['metrics'];timing=case['timing']
        rows[arm]=dict(core_advance_s=timing['core_ns']/1e9,
            restore_s=timing['restore_ns']/1e9,observation_s=timing['observation_ns']/1e9,
            checkpoint_save_s=timing['checkpoint_save_ns']/1e9,
            nodes=m['nodes'],edges=m['edges'],local_audit=m.get('local_audit'),retention=m.get('retention'))
    result=dict(schema='threemind.e67-performance-review/1',core_advanced=False,
        scope='Preserved engineering preflight and incomplete /4 formal teaching; no new /4 trial and no /4 score.',
        preflight_source=str(args.preflight),preflight_sha256=sha(args.preflight),preflight=rows,partial_formal_4=partial,
        source_findings=[
            dict(path='crates/threemind-core/src/local.rs',function='advance_impl / inhibition',
                 fact='Every inhibitory message settles and clones the receiving node, even when other messages share its timestamp.',
                 interpretation='Dense fan-out can cause many repeated receiver settlements; measure attribution before assigning an exact fraction.'),
            dict(path='crates/threemind-core/src/local.rs',function='receive / associate',
                 fact='Each actual packet forms its own recipient cohort; associate iterates all ordered pairs in that cohort.',
                 interpretation='The work grows with each cohort squared and is repeated per packet. Removing learning opportunities would change dynamics.'),
            dict(path='crates/threemind-core/src/local.rs',function='event / advance_impl / settle_edge / timer',
                 fact='Internal packets use JSON values with cloning/decoding, cloned node/edge structs and repeated timer-map updates.',
                 interpretation='Candidate implementation overhead; typed events and equivalent local-state batching need trajectory-equivalence checks.'),
            dict(path='crates/threemind-core/src/local.rs',function='edge_timer / expiry',
                 fact='The stability option schedules per-edge discrete updates at the propagation interval.',
                 interpretation='Existing preflight has more expiry checks, but does not establish the eventual shape/color cost or grade of the unborn formal arm.'),
        ],profiled_function_percentages=False)
    output=work/'analysis/deferred-4-performance.json';output.parent.mkdir(exist_ok=True)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if output.exists() and read(output)!=result:raise ValueError('preserve existing performance review edition')
    output.write_text(text,encoding='utf-8')
    print(json.dumps({'output':str(output),'partial_formal_4':partial},ensure_ascii=False))


if __name__=='__main__':main()
