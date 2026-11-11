"""Real Core forks: intervene on activation only, never on live decoder output."""
import copy
from experiment import (study,Case,WORK,old,new_json,cached,probe,evaluate_frozen,DetailedClassroom,write_gzip)


def prepare(s,h,mode):
    case=Case(s,f'F-s223-h{h}-{mode}')
    source=old.read_gzip(WORK/f'cases/B-s223-p1-h{h}-teach/checkpoint.json.gz')
    donor=old.read_gzip(WORK/f'cases/B-s223-p1-h{1-h}-teach/checkpoint.json.gz')
    state=copy.deepcopy(source);channels=DetailedClassroom(91,resolution=4).channels
    nodes={int(n['channel']):n for n in state['core']['nodes']}
    other={int(n['channel']):n for n in donor['core']['nodes']}
    marker=[c for c in channels[264:270] if c in nodes]
    selected=[c for c in channels[256:264] if c in nodes][:len(marker)] if mode=='swap-body' else marker
    if len(selected)!=len(marker):raise ValueError('matched receptor count')
    changes=[]
    for channel in selected:
        n=nodes[channel];before=n['activation']
        after=0. if mode=='clear-marker' else other[channel]['activation']
        n['activation']=after;changes.append({'channel':channel,'node':n['id'],'before':before,'after':after})
    write_gzip(case.path/'checkpoint.json.gz',state);new_json(case.path/'receipt.json',changes)
    case.finish({'history':h,'mode':mode,'field':'activation','count':len(changes),
       'retained':'all other node fields, connections, operator state, queues, clock, energy and sensory mapping'})


def main():
    s=study()
    try:
        s.allow_extension()
        for mode in ('clear-marker','swap-marker','swap-body'):
            for h in (0,1):
                key=f'F-s223-h{h}-{mode}'
                if not cached(key):prepare(s,h,mode)
                if not cached(key+'-test-normal'):probe(s,key,h,'test',common_key='B-s223-p1-h0-teach')
            key=f'F-s223-score-{mode}'
            if not cached(key):evaluate_frozen(s,223,[f'F-s223-h{h}-{mode}-test-normal' for h in (0,1)],key)
    finally:s.db.close()


if __name__=='__main__':main()
