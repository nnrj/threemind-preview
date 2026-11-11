import importlib.util
from pathlib import Path
from collections import defaultdict


def load_protocol():
    path=Path(__file__).parents[1]/'lab/explorations/2026-10-06-vision-correction/experiment.py'
    spec=importlib.util.spec_from_file_location('e56_protocol_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_balanced_requests_and_separate_teaching_views():
    e=load_protocol()
    for split,n in [('calibration',48),('practice',12),('test',24)]:
        rows=e.tasks(split);assert len(rows)==n
        groups=defaultdict(list)
        for row in rows:groups[row['category'],row['scene']].append(row)
        for group in groups.values():
            assert sorted(r['slot'] for r in group)==[0,1,2,3]
            assert all(r['items']==group[0]['items'] and r['start']==group[0]['start'] for r in group)
            assert len({r['text'] for r in group})==4
            if group[0]['category']=='pair':
                items=group[0]['items']
                assert len(set(s for s,c in items))==len(set(c for s,c in items))==2
    a={r['variant'] for r in e.tasks('calibration')}
    b={r['variant'] for r in e.tasks('practice')}
    c={r['variant'] for r in e.tasks('test')}
    assert not (a&b or a&c or b&c)
