"""Independent sustained-instrument file/time/update audit; no engine loading."""
import argparse
import gzip
import json
from pathlib import Path
import pilot_m2 as m
from m4_instrument_audit_v3 import stored_canonical


def audit(work):
    status=m.read(work/'status.json');assert status['state']=='awaiting-analysis' and status['completed']==5
    assert not any((work/n).exists() for n in ('STOP','in-flight.json'))
    m.frozen_check(work)
    birth,_=stored_canonical(work/'birth')
    assert birth['identity']=='m4-capacity-v1' and birth['seed']==1117002
    assert birth['cursor']==0 and int(birth['session']['core']['time_us'])==0 and not birth['session']['core']['nodes']
    paths=[];ticks=updates=0
    expected=(((.20,-.10),(0.,0.)),((0.,0.),(.20,.10)),((-.15,.12),(-.15,.18)))
    for segment in range(5):
        folder=work/'segments'/f's{segment}';state,receipt=stored_canonical(folder/'whole')
        rows=json.loads(gzip.decompress((folder/'trajectory.json.gz').read_bytes()))
        learning=m.read(folder/'calibration.json');r=m.read(folder/'result.json')
        start=segment*6_000_000;end=start+6_000_000
        assert len(rows)==120 and len(learning)==4 and r['segment']==segment
        assert receipt['time_us']==int(state['session']['core']['time_us'])==r['time_us']==end
        assert state['cursor']==(segment+1)*120
        assert state['motor']['committed']==state['motor']['computed']==r['motor_updates']==(segment+1)*8
        assert state['words']['committed']==state['words']['computed']==r['word_updates']==0
        assert len(state['corpus'])==(segment+1)*4
        assert state['seed']==birth['seed'] and state['text_seed']==birth['text_seed'] and state['layout']==birth['layout']
        assert [round(x['observation']['time_s']*1e6) for x in rows]==list(range(start,end,50_000))
        assert [int(x['activity']['time_us']) for x in rows]==list(range(start+50_000,end+1,50_000))
        assert {int(x['stimulus']['time_us']) for x in rows}=={0}
        for i,row in enumerate(rows):
            eye,hand=expected[((segment*120+i)//60)%3]
            assert row['eye_action']==list(eye) and row['hand_action']==list(hand)
        for j,cal in enumerate(learning,1):
            assert cal['step']==segment*120+j*30 and cal['sim_time_us']==start+j*1_500_000
            assert cal['update']['updates']==2 and cal['update']['committed_updates']==segment*8+j*2
        if segment==2:assert r['restored']['equal'] and r['restored']['canonical_sha256']==receipt['canonical_sha256']
        else:assert r['restored'] is None
        paths.append(r);ticks+=len(rows);updates+=sum(x['update']['updates'] for x in learning)
    resources=m.read(work/'resource-summary.json')
    limits={'commit':5,'ram':4,'system_disk':5,'data_disk':25}
    criteria={'complete_30_seconds':ticks==600,'exact_40_updates':updates==40,
              'complete_restoration':paths[2]['restored']['equal'],
              'private_under_3GiB':resources['peak_private_bytes']<=3*2**30,
              'host_under_600_seconds':resources['wall_seconds']<=600,
              'system_reserves':all(resources['minimum_available_bytes'][k]>=v*2**30 for k,v in limits.items()),
              'originals_under_512MiB':sum(p.stat().st_size for p in work.rglob('*') if p.is_file())<=512*2**20}
    report={'schema':'threemind.m4-capacity-file-audit/1','passed':True,'whole_states':6,'ticks':ticks,
            'peripheral_updates':updates,'scientific_origins':0,'Core_loaded':False,'simulation_advanced':False}
    m.original(work/'audit-v1.json',report)
    analysis={'schema':'threemind.m4-capacity-analysis/1','valid':True,'verdict':'PASS' if all(criteria.values()) else 'FAIL',
              'criteria':criteria,'segments':paths,'scientific_origins':0,'resources':resources}
    m.original(work/'analysis-v1.json',analysis)
    print(json.dumps({'audit':report,'analysis':analysis}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work.resolve())
