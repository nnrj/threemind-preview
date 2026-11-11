"""Prospective case-table checks; no creation or advancement of a Core."""
from collections import Counter
from stimulus_assay import cases,profile

def test_declared_cases_and_paired_information():
    rows=cases()
    assert len(rows)==len({c['key'] for c in rows})==960
    assert Counter(c['origin'] for c in rows)=={i:120 for i in range(8)}
    assert Counter(c['family'] for c in rows)=={'strong':576,'novelty':384}
    assert len({tuple(sorted(profile(i,'strong').items())) for i in range(8)})==8
    assert len({tuple(sorted(profile(i,'novelty').items())) for i in range(8)})==8
    for row in rows:
        opposite=[r for r in rows if r['key'].rsplit('/',1)[0]==row['key'].rsplit('/',1)[0] and r['cue']!=row['cue']]
        assert len(opposite)==1
        assert all(row[k]==opposite[0][k] for k in ('seed','curve','relaxation','family','arm','delay','profile'))

def test_strong_actual_drive_is_matched():
    for i in range(8):
        p=profile(i,'strong')
        assert (p['drive']/p['strong_intensity'])*p['strong_intensity']==p['drive']
        assert p['strong_intensity']>1
