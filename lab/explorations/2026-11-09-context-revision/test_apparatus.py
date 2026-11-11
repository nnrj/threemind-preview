"""Isolated instrument checks; no historical subjects or scientific origins."""
import argparse
import gc
import inspect
import json
from pathlib import Path
import time
import experiment as e
import analyze as a


def main(work,attempt):
    e.deterministic();folder=work/'instrument'/f'attempt-{attempt:02d}'
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'started.json').exists():raise RuntimeError('instrument already attempted; preserve and audit before a new attempt')
    instrument_seed=26110800+attempt
    e.save(folder/'started.json',dict(source_manifest=e.manifest(),seed=instrument_seed))
    passed=[]
    def ok(name):passed.append(name);print(json.dumps(dict(check=name)),flush=True)
    assert 'case' not in inspect.signature(e.CalibratedActivity.predict).parameters
    assert tuple(e.PORTS)==('sound','vision','action')
    assert e.INDEX==[0,3,5,8,11,14,16,19];ok('complete-window interface contract')
    for h in range(2):
        f=e.materials(26110800,h,True);d=e.materials(26110800,h,False)
        assert len(f)==24 and set(x['dose'] for x in f).isdisjoint(x['dose'] for x in d)
        assert sum(x['kind']=='old' for x in f)==4
        assert sum(x['kind']=='ambiguous' for x in f)==12
        assert sum(x.get('conflict',False) for x in f)==4
    assert [e.sensory(x) for x in e.materials(26110800,0,True)]==[e.sensory(x) for x in e.materials(26110800,1,True)]
    ok('prospective materials and history-blind current cues')
    for actual in (0,1):
        w=dict(actual=actual,automatic_view=False,view_strength=.84)
        assert e.feedback(w,0,'intact')=={}
        assert e.feedback(w,2,'intact')=={f'D{actual}':.84}
        assert e.feedback(w,2,'view-blocked')=={}
        assert e.feedback(w,0,'forced-view')=={f'D{actual}':.84}
    ok('action-controlled sensory consequences')
    with e.Guard(folder):
        s=e.Student(instrument_seed,'context-instrument');s.checkpoint(folder,'birth.json.gz')
        born=e.load(folder/'birth.json.gz');r=s.window({'Z0':.8});final=s.state()
        t=e.Student.restore(folder,born);r2=t.window({'Z0':.8},observed=True)
        assert r==r2 and e.base.digest(final)==e.base.digest(t.state());ok('observation-frequency invariance')
        before=t.state();time.sleep(.03);assert before==t.state();ok('wall time does not advance subject')
        t.checkpoint(folder,'window.json.gz');u=e.Student.restore(folder,e.load(folder/'window.json.gz'))
        assert t.window({'Z1':.8})==u.window({'Z1':.8});assert e.base.digest(t.state())==e.base.digest(u.state())
        ok('complete restore and next question')
        del s,t,u;gc.collect()
        s=e.Student.restore(folder,born);previous=None
        for stage in range(3):
            if previous and previous['ready']:break
            previous=e.unit(folder,f'calibration-{stage}',s,lambda stage=stage:e.calibrate_unit(s,stage,previous))
        interface=previous['valid'];ok('bounded spaced teaching, corrections and persistent adapters executed')
        s.checkpoint(folder,'interface-parent.json.gz');parent=e.load(folder/'interface-parent.json.gz')
        samples=s.samples[:16]
        before=s.core.capture_state().to_dict()
        z=s.adapters['action']
        z.continue_calibration([[r['question']['frames']['action'][j] for j in e.INDEX] for r in samples],
                              [r['case']['label'] for r in samples],steps=1)
        assert before==s.core.capture_state().to_dict()
        expected=s.adapter_digest();u=e.Student.restore(folder,parent);z=u.adapters['action']
        z.continue_calibration([[r['question']['frames']['action'][j] for j in e.INDEX] for r in samples],
                              [r['case']['label'] for r in samples],steps=1)
        assert expected==u.adapter_digest();ok('next optimizer update and RNG preserved; Core unchanged')
        del s,u;gc.collect()
        s=e.Student.restore(folder,parent);s.frozen_digest=s.adapter_digest()
        result=e.unit(folder,'new-teaching-0',s,lambda:e.new_unit(s,0,0,None))
        s.checkpoint(folder,'trained.json.gz');trained=e.load(folder/'trained.json.gz')
        before=s.core.capture_state().to_dict();mask=e.intervention(s,'restored')
        assert before==s.core.capture_state().to_dict();ok('silence and restoration exact')
        e.save(folder/'mask.json',mask)
        exemplar={}
        for c in e.materials(s.seed,0,True):
            if c['kind'] not in exemplar:exemplar[c['kind']]=c
        rows=[]
        for c in exemplar.values():
            r=e.trial(s,c,observed=True);a.verify_trial(r,s.state());rows.append(r)
        e.save(folder/'three-trials.json.gz',rows);s.checkpoint(folder,'three-trials.json.gz.state.json.gz')
        ok('independent event, temporal port and feedback arithmetic')
        x=e.Student.restore(folder,trained);y=e.Student.restore(folder,trained)
        e.intervention(x,'restored');case=e.materials(s.seed,0,True)[0]
        rx=e.trial(x,case);ry=e.trial(y,case)
        assert rx==ry;ok('restored causal branch repeats complete raw trajectory')
        result=dict(passed=bool(interface),checks=passed,source_manifest=e.manifest(),
                    calibration=dict(correct=previous['correct'],n=previous['n'],valid=interface),
                    new_development=dict(correct=result['correct'],n=result['n']),
                    matching_valid=mask['matching_valid'],instrument_seed=instrument_seed,
                    classification='apparatus only; excluded from scientific N')
        e.save(folder/'summary.json',result)
        assert e.load(folder/'started.json')['source_manifest']==e.manifest()
        if result['passed']:
            receipt=dict(summary=(folder/'summary.json').relative_to(work).as_posix(),sha256=e.sha(folder/'summary.json'))
            e.save(folder/'verified-receipt.json',receipt)
            previous=work/'instrument/verified.json'
            if previous.exists():e.save(folder/'previous-verified-receipt.json',e.load(previous))
            e.base.atomic_json(previous,receipt)
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);p.add_argument('--attempt',type=int,default=1)
    args=p.parse_args();main(args.work.resolve(),args.attempt)
