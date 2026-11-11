"""Passive live candidate archiving and parent/offspring observation summaries."""
from collections import deque
import copy
import json
from pathlib import Path
from lab.tools.ocean_species import save_live_candidate
from lab.tools.ocean_turning import TurningObserver


class CultureWatch:
    def __init__(self,root,case,project,*,state=None,archive_prefix='E39',
                 consumption_kinds=('body_engulfed',)):
        self.root=Path(root);self.case=case;self.project=project;self.observer=TurningObserver()
        self.stats={};self.markers=set();self.stream=None
        self.archive_prefix=archive_prefix;self.consumption_kinds=consumption_kinds
        if state:
            self.stats={int(k):copy.deepcopy(v) for k,v in state['stats'].items()}
            self.markers={tuple(v) for v in state['markers']}
            self.observer.history={int(k):deque((int(t),tuple(r),tuple(a)) for t,r,a in v)
                                   for k,v in state['history'].items()}
            self.observer.last_hit={int(k):v for k,v in state['last_hit'].items()}

    def item(self,i):
        return self.stats.setdefault(i,{'observed_us':0,'turns':0,'captures':0})

    def improved(self,world,i,field):
        b=world.bodies[i];child=self.item(i)
        if b.parent is None:return False
        parent=self.item(b.parent);minimum=3 if field=='turns' else 2
        if min(child['observed_us'],parent['observed_us'])<60_000_000 or child[field]<minimum:return False
        return child[field]/child['observed_us']>=2*parent[field]/parent['observed_us']

    def log(self,value):
        if self.stream is None:
            self.stream=(self.root/'cases'/self.case/'observer-events.jsonl').open('x',encoding='utf-8')
        self.stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');self.stream.flush()

    def observe(self,world,row,active_before):
        for i in active_before:self.item(i)['observed_us']+=world.p.period_us
        changed={};hits=self.observer.observe(row)
        for hit in hits:
            i=hit['individual'];self.item(i)['turns']+=1
            changed.setdefault(i,[]).append({'kind':'turning_food','summary':'Motor turn followed by nutrient intake',**hit})
        for event in row['events']:
            if event['kind'] in self.consumption_kinds:
                i=event['predator'];self.item(i)['captures']+=1
                changed.setdefault(i,[]).append(event|{'summary':
                    'Complete enclosure consumption' if event['kind']=='body_engulfed' else 'Recorded coverage-based consumption'})
        for i,evidence in sorted(changed.items()):
            score=self.item(i);flags=[]
            if score['turns'] in (1,3,6,12,24,48):flags.append('turns-'+str(score['turns']))
            if any(e['kind'] in self.consumption_kinds for e in evidence):flags.append('capture-'+str(score['captures']))
            if score['turns'] and score['captures']:flags.append('both')
            for field in ('turns','captures'):
                if self.improved(world,i,field):flags.append('improved-'+field)
            flags=[f for f in flags if (i,f) not in self.markers]
            record={'time_us':world.time_us,'individual':i,'cohort':world.cohorts[i],
                    'generation':world.bodies[i].generation,'events':evidence,'counts':dict(score),'flags':flags}
            if flags and world.bodies[i].physical and world.engines[i].life!='dead':
                parent=world.bodies[i].parent
                evidence.append({'kind':'parent-comparison','summary':'Observed rate comparison, not matched causal proof',
                    'child':dict(score),'parent_id':parent,
                    'parent':dict(self.item(parent)) if parent is not None else None,
                    'minimum_observed_us':60_000_000,'minimum_turns':3,'minimum_captures':2,'rate_ratio_min':2})
                out=self.root/'event-species'/f'{self.case}-{world.time_us}-{i}.tmspecies'
                save_live_candidate(world,i,out,name=f'{self.archive_prefix} {world.cohorts[i]} #{i} · '+', '.join(flags),
                    evidence=evidence,source={'project':self.project,'case':self.case,'record':'observed-end-of-step'},
                    description='Live full-habitat culture candidate; observational capability evidence.')
                record['bundle']=str(out)
                self.markers.update((i,f) for f in flags)
                print(json.dumps({'candidate_saved':{k:v for k,v in record.items() if k!='events'}}),flush=True)
            elif flags:
                record['archive_skipped']='not a living body at end of event step'
            self.log(record)

    def capture(self):
        return {'schema':'threemind.ocean-culture-observer/1','stats':copy.deepcopy(self.stats),
                'markers':sorted(self.markers),'history':{i:list(v) for i,v in self.observer.history.items()},
                'last_hit':self.observer.last_hit}

    def close(self):
        if self.stream:self.stream.close()
