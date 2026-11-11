import copy
from m2_gain_analyze import score
import m2_gain_rig as spec


def synthetic():
    hs=[]
    for h in (0,1):
        rs=[]
        for d in spec.DELAYS:
            for q in spec.DOSES:
                v=(1-2*h)*.005 if q>.6 else 0.
                direction=int(v>1e-4)-int(v<-1e-4)
                rs.append({'dose':q,'delay':d,'prediction':{'direction':direction,'endpoint':v},
                           'probe':{'direction':direction,'first':v},'comparison':{'direction':direction}})
        hs.append({'history':h,'tests':rs})
    return {'origin':0,'histories':hs}


def test_complete_prediction_gate_not_average_accuracy():
    data=synthetic();assert score(data)['qualified']
    wrong=copy.deepcopy(data);wrong['histories'][0]['tests'][0]['prediction']['direction']=1
    assert not score(wrong)['qualified']
    wrong=copy.deepcopy(data);wrong['histories'][0]['tests'][-1]['prediction']['endpoint']+=2e-6
    assert not score(wrong)['qualified']


def test_both_nonblank_classes_required():
    data=synthetic()
    for h in data['histories']:
        for r in h['tests']:
            r['prediction']={'direction':0,'endpoint':0.};r['probe']={'direction':0,'first':0.}
    assert not score(data)['qualified']


def test_source_and_material_separation():
    assert len(set(spec.SEEDS))==8 and not set(spec.SEEDS)&{spec.APPARATUS_SEED,spec.TEST_SEED}
    assert not set(spec.DELAYS)&{0,2}
    assert not (set(spec.DOSES)-{0.})&{.4,.47,.55,.57,.63,.73,.8}
    assert sum(len(h['tests']) for h in synthetic()['histories'])==20


def test_absolute_host_guard_finalizes_without_simulation():
    import subprocess,sys
    from uuid import uuid4
    import m2_gain_driver as driver
    import pilot_m2 as m
    work=m.ROOT/'.work'/('m2-gain-guard-finalize-'+uuid4().hex)
    work.mkdir()
    assert driver.WORK.is_absolute()
    code='from pathlib import Path; import sys; import pilot_m2 as m\nw=Path(sys.argv[1]).resolve()\nwith m.Guard(w) as guard:\n assert guard.thread.is_alive()\nassert not (w/"STOP").exists()\n'
    # The scientific host is a fresh Python process, without pytest's plugins.
    subprocess.run([sys.executable,'-X','utf8','-c',code,str(work)],cwd=driver.HERE,check=True)
    assert not (work/'STOP').exists()
    summary=m.read(work/'resource-summary.json')
    assert summary['wall_seconds']>=0 and summary['peak_private_bytes']>0
