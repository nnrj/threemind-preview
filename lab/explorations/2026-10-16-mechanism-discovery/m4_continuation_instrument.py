"""Known-course N=0 check: uninterrupted versus new-process complete resume.

Only the dedicated instrument path/seed is accepted; no formal M4 subject is
loaded or advanced. Two frozen balanced blocks and 240 updates per final copy.
"""
import argparse,gc,hashlib,json,os,time
from pathlib import Path
import torch
import pilot_m2 as m
import m4_balanced_rig_v2 as rig
import m4_stage_continuation as cont
from m4_continuation_host import Guard,WORK,REL

ROOT=WORK/REL/'instrument'
SEED=1123010


def run(mode):
    torch.set_num_threads(1)
    root=ROOT.resolve();w=root/mode
    with m.worker_lock(m.DEFAULT_WORK):
        if w.exists():raise FileExistsError('one attempt per instrument path')
        w.mkdir(parents=True);m.original(w/'apparatus-in-flight.json',{'mode':mode,'pid':os.getpid(),'seed':SEED,'epoch':time.time()})
        with Guard(w,w,private_gib=3,remaining_seconds=600) as guard:
            if mode=='baseline':
                u=rig.Unit(w,0,guard,lambda v:None)
                u.begin('birth');u.a=rig.Subject(SEED,identity='m4-stage-continuation-instrument',data_root=u.folder)
                u.classes=rig.metrics.channel_classes(u.a.session.world.channels,u.a.session.world.vision_width)
                m.original(u.folder/'channel-classes.json',u.classes);u.end('birth')
                u.trials('teach-0-0',u.bank['teaching_rounds'][0][0],teaching=True,calibrate=True)
                # Keep this complete, developing object for the baseline.
                u.trials('teach-0-1',u.bank['teaching_rounds'][0][1],teaching=True,calibrate=True)
            else:
                src=root/'baseline/units/o0';dst=w/'units/o0';dst.mkdir(parents=True)
                assert not (root/'baseline/apparatus-in-flight.json').exists()
                assert not (root/'baseline/STOP').exists()
                names=['cases.json','channel-classes.json','boundaries/teach-0-0.json','stages/teach-0-0.json']
                r=m.read(src/'states/teach-0-0/complete.json')
                names += ['states/teach-0-0/'+p for p in ['complete.json',*r['files']]]
                names += [v['path'] for v in r['dependencies']]
                for name in names:
                    source=(src/name).resolve();target=(dst/name).resolve()
                    assert source.is_relative_to(src.resolve()) and target.is_relative_to(dst.resolve())
                    target.parent.mkdir(parents=True,exist_ok=True);os.link(source,target)
                u=cont.attach_unit(w,0,guard,lambda v:None)
                u.a=rig.Subject.restore(dst/'states/teach-0-0',data_root=dst)
                assert rig.digest(u.a.canonical())==r['canonical_sha256'] and u.a.session.engine.time_us==9_000_000
                m.original(w/'restoration.json',{'canonical_sha256':r['canonical_sha256'],'exact':True,'fresh_process':True,
                           'time_us':9000000,'source_pid':m.read(root/'baseline/host.json')['pid'],'pid':os.getpid()})
                u.trials('teach-0-1',u.bank['teaching_rounds'][0][1],teaching=True,calibrate=True)
            assert u.a.session.engine.time_us==18_000_000 and u.a.motor.committed_updates==240
            m.original(w/'host.json',{'pid':os.getpid(),'epoch':time.time(),'seed':SEED,'scientific_origins':0})
            m.original(w/'result.json',{'canonical_sha256':rig.digest(u.a.canonical()),'time_us':18000000,
                       'motor_updates':240,'trajectory_hashes':m.read(u.folder/'stages/teach-0-1.json')['trajectory_hashes']})
            del u;gc.collect()
        assert not (w/'STOP').exists() and not (w/'in-flight.json').exists()
        (w/'apparatus-in-flight.json').unlink()
        print(json.dumps(m.read(w/'result.json')),flush=True)


def verify():
    from m4_balanced_audit_v2 import whole
    assert not (ROOT/'verification.json').exists()
    records=[]
    for mode in ('baseline','resumed'):
        w=ROOT/mode;assert not (w/'STOP').exists() and not (w/'apparatus-in-flight.json').exists()
        s,r=whole(w/'units/o0/states/teach-0-1',w/'units/o0')
        assert s['identity']=='m4-stage-continuation-instrument' and s['seed']==SEED
        assert s['motor']['computed']==s['motor']['committed']==240 and int(s['session']['core']['time_us'])==18_000_000
        records.append(m.read(w/'result.json'));del s;gc.collect()
    assert records[0]==records[1]
    assert m.read(ROOT/'baseline/host.json')['pid']!=m.read(ROOT/'resumed/host.json')['pid']
    result={'passed':True,'schema':'threemind.m4-stage-continuation-instrument/1','scientific_origins':0,'seed':SEED,
            'ordinary_and_new_process_resume_identical':True,'complete_state_and_trajectory_exact':True,
            'time_us_per_final':18000000,'motor_updates_per_final':240,'result':records[0],
            'current_formal_subject_loaded':False,'current_formal_subject_advanced':False}
    m.original(ROOT/'verification.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('baseline','resumed','verify'));a=p.parse_args()
    verify() if a.command=='verify' else run(a.command)
