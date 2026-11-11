"""Prospective shared-world probes within the same aggregate study budget."""
import argparse
import gzip
import json
import time
import psutil
from experiment import WORK,OLD,study
from lab.tools.ocean_behavior import select_region
from lab.tools.ocean_contact_cli import load,save
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_encounter import ActivityHistory,candidate,observe_encounter


def run(group):
    s=study();root=WORK/'natural'/f'g{group}';root.mkdir(parents=True,exist_ok=True)
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    def guard():
        s.guard()
        done=sum(read_json(p)['wall_seconds'] for p in (WORK/'natural').glob('**/result.json'))
        # The other bounded worker's unfinished local case is at most 900 s.
        if s.completed_wall+done+time.monotonic()-clock.born_wall+900>21600:raise RuntimeError('aggregate simulation budget')
        memory=0
        for process in psutil.process_iter(['name','cmdline','memory_info']):
            command=process.info['cmdline'] or []
            if any('2026-10-03-ocean-behavior' in c and c.endswith(('experiment.py','natural.py')) for c in command):
                memory+=process.info['memory_info'].rss
        if memory>4*2**30:raise RuntimeError('combined simulation workers memory budget')
    try:
        scout=root/'scout'
        if not (scout/'result.json').exists():
            if scout.exists():raise RuntimeError('partial scout preserved')
            scout.mkdir();w=load(OLD/'cases'/f'g{group}-core'/'checkpoints/200000000')
            origin=w.time_us;history=ActivityHistory();found={};events=[];born=time.monotonic()
            with gzip.open(scout/'inputs.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as out:
                def record(row):out.write(json.dumps(row,separators=(',',':'))+'\n')
                while w.time_us<origin+60000000:
                    if (w.time_us-origin)%1000000==0:
                        try:guard()
                        except BaseException as exc:
                            save(w,scout/'interrupted')
                            write_json(scout/'result.json',{'status':'paused_guard','error':str(exc),'found':found,
                                'wall_seconds':time.monotonic()-born,'observed_us':w.time_us-origin})
                            raise
                    history.sample(w,origin)
                    if w.time_us>=origin+2000000:
                        for task in ('food','hunt','escape'):
                            if task in found:continue
                            event=candidate(w,task)
                            if not event:continue
                            folder=root/task;folder.mkdir()
                            image=w.engines[event['focal']].capture_state()
                            rows=list(history.activity.get(event['focal'],[]))
                            plan=select_region(image,rows)
                            save(w,folder/'source')
                            with gzip.open(folder/'selection-activity.json.gz','wt',encoding='utf-8') as stream:json.dump(rows,stream,separators=(',',':'))
                            write_json(folder/'selection.json',{'encounter':event,'plan':plan})
                            found[task]={'time_us':w.time_us,'focal':event['focal'],'target':event['target'],'applicable':plan['applicable']}
                            print(json.dumps({'group':group,'trigger':task,**found[task]}),flush=True)
                    if len(found)==3:break
                    w.step(record)
            save(w,scout/'final')
            write_json(scout/'result.json',{'status':'prospective_selection_complete','found':found,
                'not_triggered':[t for t in ('food','hunt','escape') if t not in found],
                'wall_seconds':time.monotonic()-born,'observed_us':w.time_us-origin})
        scouting=read_json(scout/'result.json')
        if scouting['status']!='prospective_selection_complete':raise RuntimeError('incomplete scout retained; separate continuation required')
        found=scouting['found']
        for task in ('food','hunt','escape'):
            if task not in found or not found[task]['applicable']:continue
            folder=root/task;selection=read_json(folder/'selection.json')
            for op in ('intact','target','matched'):
                if (folder/op/'result.json').exists():continue
                guard();w=load(folder/'source');event=selection['encounter']
                if op!='intact':w.engines[event['focal']].intervene(edges=selection['plan'][op+'_edges'],action='silence')
                clock.born_wall=time.monotonic()
                r=observe_encounter(w,folder/op,event,op,guard=guard)
                print(json.dumps({'group':group,'task':task,'op':op,'food':r['food'],'captured':r['captured'],
                    'physical':r['physical'],'wall_seconds':r['wall_seconds']}),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1));a=p.parse_args()
    for g in ((0,1) if a.group is None else (a.group,)):run(g)
