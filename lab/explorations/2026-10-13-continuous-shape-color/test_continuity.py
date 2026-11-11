"""Engineering fixtures, never formal experimental subjects or score evidence."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import torch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('e68_experiment',HERE/'experiment.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Records:
    def append(self,*a,**k): pass


def fixture(tmp_path,monkeypatch):
    torch.set_num_threads(2)
    monkeypatch.setattr(m,'device',lambda:'cpu')
    monkeypatch.setattr(m.ContinuousArm,'guard',lambda _:None)
    return SimpleNamespace(work=tmp_path,recorder=Records(),rid=lambda v:v,attach=lambda *a,**k:None,sync=lambda:None)


@pytest.mark.parametrize('arm',['2','3.1'])
def test_questions_teaching_and_fitting_keep_one_current_state(tmp_path,monkeypatch,arm):
    s=fixture(tmp_path,monkeypatch);a=m.ContinuousArm(s,arm,engineering=True)
    original=id(a.a);tasks=m.initial_calibration()[:2]
    a.collect('cal',tasks)
    assert a.a.session.engine.time_us==2000000
    assert [x['start_us'] for x in m.read(a.base/'cal/predictions.json')]==[0,1000000]
    # No restore is permitted anywhere inside a stage or between ordinary stages.
    def forbidden(*args,**kwargs):raise AssertionError('unexpected restore')
    monkeypatch.setattr(m.RecognitionSystem,'restore',forbidden)
    before=m.encoded(a.a.session.snapshot())
    a.fit('initial-fit',['cal'])
    assert m.encoded(a.a.session.snapshot())==before
    assert a.a.words.computed_updates==a.a.words.committed_updates==1200
    a.teach('lesson',[tasks[0]|dict(operation='review',gap_s=0)])
    a.collect('dev',tasks)
    assert id(a.a)==original and a.a.session.engine.time_us==5500000
    chain=[m.read(p) for p in sorted((a.base/'chain').glob('*.json'))]
    assert all(b['parent']==c['boundary_sha256'] and b['start_us']==c['end_us'] for c,b in zip(chain,chain[1:]))
    assert a.a.session.world.time_s==pytest.approx(5.5)
    assert len(a.a.session.history)==32


def test_uncertain_operation_never_silently_replays(tmp_path,monkeypatch):
    s=fixture(tmp_path,monkeypatch);a=m.ContinuousArm(s,'2',engineering=True)
    def interrupted():
        a.a.session.tick()
        raise RuntimeError('after real input')
    with pytest.raises(RuntimeError,match='after real input'): a.unit('probe',interrupted)
    assert a.flight.exists() and a.a.session.engine.time_us==50000
    with pytest.raises(m.ContinuityUncertain,match='ask user'):m.ContinuousArm(s,'2')


@pytest.mark.parametrize('arm',['2','3.1'])
def test_clean_boundary_resumes_exact_next_input_not_completed_question(tmp_path,monkeypatch,arm):
    s=fixture(tmp_path,monkeypatch);a=m.ContinuousArm(s,arm,engineering=True)
    tasks=m.initial_calibration()[:2];a.collect('cal',tasks)
    b=m.ContinuousArm(s,arm)
    assert b.pointer==a.pointer
    # Reentering completed collection must not repeat it.
    b.collect('cal',tasks)
    assert b.a.session.engine.time_us==2000000
    left=a.a.session.tick();right=b.a.session.tick()
    assert left==right
    assert a.a.session.engine.capture_state().digest==b.a.session.engine.capture_state().digest
