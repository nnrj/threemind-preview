"""File-only state/clock/corpus/lineage and independent behavior arithmetic."""
import argparse,copy,gc,gzip,hashlib,json
from pathlib import Path
import numpy as np
import pilot_m2 as m
import m4_balanced_course as course
import m4_regional_metrics as metrics
from m4_instrument import digest
from m4_compact_subject_v2 import stored_canonical
import m4_compact_evidence_v2 as codec
from m4_balanced_analyze import evaluate


def readgz(path):return codec.read(path) if path.suffix=='.xz' else json.loads(gzip.decompress(path.read_bytes()))


def whole(folder,data_root):
    state,receipt=stored_canonical(folder)
    assert state['schema']=='threemind.regional-eye-hand-whole/2' and state['corpus']==receipt['dependencies']
    for ref in state['corpus']:
        path=(data_root/ref['path']).resolve();assert path.is_relative_to(data_root.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==ref['sha256']
        with np.load(path,allow_pickle=False) as z:
            assert set(z.files)=={'x','eye','hand','move'} and all(len(z[k])==ref['examples'] for k in z.files)
            assert z['x'].shape[1:]==(8,4*len(state['layout'])) and np.isfinite(z['x']).all()
    return state,receipt


def independent_scores(task,rows,result,start):
    assert len(rows)==60 and [int(r['activity']['time_us']) for r in rows]==list(range(start+50000,start+3000001,50000))
    assert [round(r['observation']['time_s']*1e6) for r in rows]==list(range(start,start+3000000,50000))
    assert all(int(r['stimulus']['time_us'])==0 for r in rows)
    assert result['start_us']==start and result['end_us']==start+3000000
    obs=[r['observation'] for r in rows];first=obs[0];eye0=np.array(first['eye_angle_rad']);p0=np.array([first['pointer']['x'],first['pointer']['y']])
    inside=[];eye=[];hand=[];hold_eye=[];hold_hand=[];ec=[];hc=[]
    for ob in obs:
        c=ob['camera'];delta=np.array([*task['xy'],.16])-c['origin_m'];depth=delta@c['forward']
        extent=max(abs(delta@c['right']/depth),abs(delta@c['up']/depth));p=ob['pointer']
        d=float(np.linalg.norm(np.array([p['x'],p['y']])-task['xy']));ok=bool(depth>0 and extent<=.075)
        inside.append(ok);eye.append(ok and np.linalg.norm(ob['eye_velocity_rad_s'])<.08);hand.append(d<=.15)
        hold_eye.append(np.linalg.norm(np.array(ob['eye_angle_rad'])-eye0)<=.025 and np.linalg.norm(ob['eye_velocity_rad_s'])<.08)
        hold_hand.append(np.linalg.norm(np.array([p['x'],p['y']])-p0)<=.05 and np.hypot(p['vx'],p['vy'])<.01)
        ec.append(min(4.,extent/.075));hc.append(min(4.,d/.15))
    a=all((hold_eye if task['mode']=='hand' else eye)[-6:]);b=all((hold_hand if task['mode']=='eye' else hand)[-6:])
    assert result['eye_success']==a and result['hand_success']==b and result['joint_success']==(a and b)
    assert result['eye_initially_inside']==inside[0] and result['hand_initially_arrived']==hand[0]
    assert abs(result['eye_target_cost']-np.mean(ec[-6:]))<1e-12 and abs(result['hand_target_cost']-np.mean(hc[-6:]))<1e-12
    return 60


def audit_source(folder,origin):
    result=m.read(folder/'result.json');bank=course.bank(origin);assert m.read(folder/'cases.json')==bank
    assert result['seed']==1123100+origin and result['origin']==origin
    labels=['birth','warmup','pre']+[f'teach-{i}-{j}' for i in range(2) for j in range(8)]+['development','confirmation']
    times=[0,3000000,39000000]+[39000000+(j+1)*9000000 for j in range(16)]+[219000000,255000000]
    changes=[0,0,0]+[120*(j+1) for j in range(16)]+[1920,1920]
    corpus=[];birth=None;parent=None;receipts={};count=0;ticks=60
    warm=readgz(folder/'warmup.json.xz');assert len(warm)==60
    assert [int(x['activity']['time_us']) for x in warm]==list(range(50000,3000001,50000))
    for label,t,updates in zip(labels,times,changes):
        s,r=whole(folder/'states'/label,folder);count+=1;receipts[label]=r
        assert r['time_us']==t and s['cursor']==t//50000 and s['motor']['computed']==s['motor']['committed']==updates
        assert s['words']['computed']==s['words']['committed']==0 and s['identity']==f'm4-balanced-v2-o{origin}'
        assert s['branch'] is None
        if birth is None:
            assert not s['session']['core']['nodes'] and not s['session']['core']['edges'];birth=s
        assert s['layout']==birth['layout'] and s['seed']==birth['seed'] and s['text_seed']==birth['text_seed']
        assert s['corpus'][:len(corpus)]==corpus;corpus=s['corpus']
        if label=='confirmation':parent=s
        else:del s
        gc.collect()
    assert len(corpus)==48 and sum(x['examples'] for x in corpus)==288
    classes={int(k):v for k,v in m.read(folder/'channel-classes.json').items()}
    stage_results={};reduced={};start=3000000
    for label in labels[2:]:
        tasks=bank[label] if not label.startswith('teach') else bank['teaching_rounds'][int(label.split('-')[1])][int(label.split('-')[2])]
        stage=m.read(folder/'stages'/(label+'.json'));stage_results[label]=stage['results'];computed=[]
        assert len(stage['results'])==len(tasks);features=[]
        for task,saved in zip(tasks,stage['results']):
            path=folder/'trials'/label/task['id'];rows=readgz(path/'trajectory.json.xz')
            assert saved==m.read(path/'result.json') and saved['mode']==task['mode']
            teaching=label.startswith('teach');assert saved['teaching']==teaching and all(r['assistance']==teaching for r in rows)
            samples=m.read(path/'teaching-samples.json');assert len(samples)==(6 if teaching else 0)
            if teaching:assert all(x['move']==int(task['mode']!='eye') for x in samples)
            ticks+=independent_scores(task,rows,saved,start);start+=3000000
            if not teaching:features.append(metrics.reduce_trial(task,rows,classes))
            computed.append(digest(rows));del rows
        assert computed==stage['trajectory_hashes']
        if label.startswith('teach'):assert stage['calibration']['updates']==120
        else:
            assert digest(features)==digest(readgz(folder/'features'/(label+'.json.xz')))
            reduced[label]=features
    assert start==255000000
    selection=m.read(folder/'group-selection.json');chosen=m.read(folder/'edge-selection.json')
    pre=reduced['pre'];dev=reduced['development'];conf=reduced['confirmation']
    assert digest(metrics.fit_groups(pre,dev,classes))==digest(selection)
    config=parent['session']['core']['config']
    table=metrics.edge_table(readgz(folder/'development-graph.json.gz'),config,219000000,selection)
    assert digest(metrics.select_edges(table,selection))==digest(chosen)
    del table;gc.collect()
    # Selection files must exist before the first confirmation output.
    first=folder/'trials'/'confirmation'/bank['confirmation'][0]['id']/'trajectory.json.xz'
    assert (folder/'group-selection.json').stat().st_mtime_ns<=first.stat().st_mtime_ns
    assert (folder/'edge-selection.json').stat().st_mtime_ns<=first.stat().st_mtime_ns
    assert metrics.behavior(stage_results['confirmation'])==result['G1']
    assert metrics.confirm_groups(selection,conf)==result['G2']
    matching=m.read(folder/'matching-recheck.json');decision=m.read(folder/'pre-causal-decision.json')
    table=metrics.edge_table(readgz(folder/'confirmation-graph.json.gz'),config,255000000,selection)
    assert digest(metrics.recheck_edges(chosen,table))==digest(matching)
    del table;gc.collect()
    assert decision['eligible']==result['causal_eligible']==bool(result['G1']['qualified'] and result['G2']['qualified'] and matching['valid'])
    arms={};finals={};traces={}
    if result['causal_eligible']:
        seen=[]
        for group,pairs in chosen['groups'].items():
            assert len(pairs)==16
            for pair in pairs:
                assert metrics.within(pair['residual']);seen.append(tuple(pair['control']['key']))
        assert len(set(seen))==32 and all(metrics.within(x) for x in matching['residuals'])
        for arm in ('sham','eye','hand','matched-eye','matched-hand','restored-eye','restored-hand'):
            initial,ir=whole(folder/'states'/(arm+'-initial'),folder);final,fr=whole(folder/'states'/(arm+'-final'),folder);count+=2
            assert ir['time_us']==255000000 and fr['time_us']==291000000
            expected=copy.deepcopy(parent);expected['branch']=initial['branch'];expected['phase']='causal'
            assert initial['branch']['parent_sha256']==receipts['confirmation']['canonical_sha256']
            op=m.read(folder/'interventions'/(arm+'.json'))
            if arm in ('eye','hand','matched-eye','matched-hand'):expected['session']['core']['silenced_edges']=sorted(op['edges'])
            assert initial==expected
            assert final['motor']==parent['motor'] and final['words']==parent['words'] and final['corpus']==corpus
            assert final['branch']==initial['branch'] and final['cursor']==5820
            final['branch']=None;finals[arm]=digest(final);del initial,final,expected;gc.collect()
            rowscores=[];trace=[];start=255000000
            for task in bank['confirmation']:
                path=folder/'causal'/arm/task['id'];rows=readgz(path/'trajectory.json.xz');score=m.read(path/'result.json')
                assert not score['teaching'] and all(not r['assistance'] for r in rows)
                ticks+=independent_scores(task,rows,score,start);start+=3000000
                trace.append(digest(rows));rowscores.append(score);del rows
            arms[arm]=rowscores;traces[arm]=trace
        exact={g:finals['restored-'+g]==finals['sham'] and traces['restored-'+g]==traces['sham'] for g in ('eye','hand')}
        assert metrics.causal(arms,exact)==result['G3']
    else:assert not result['G3']['qualified'] and not result['G3']['measurable']
    assert count==result['whole_states']==(35 if result['causal_eligible'] else 21)
    assert len(list((folder/'states').glob('*/complete.json')))==count
    return {'whole_states':count,'ticks':ticks,'teaching_trials':48,'ordinary_autonomous_trials':36,
            'causal_trials':84 if result['causal_eligible'] else 0,'corpus_examples':288,'motor_updates':1920}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work.resolve()
    m.frozen_check(w);assert m.read(w/'status.json')['state']=='awaiting-analysis'
    assert not any((w/n).exists() for n in ('STOP','in-flight.json'))
    counts={};units=[]
    for i in range(8):
        f=w/'units'/f'o{i}';v=audit_source(f,i);units.append(m.read(f/'result.json'))
        for k,n in v.items():counts[k]=counts.get(k,0)+n
    assert evaluate(units)==m.read(w/'analysis-v1.json')
    out={'schema':'threemind.m4-balanced-file-audit/1','passed':True,'counts':counts,
         'scientific_origins':8,'Core_loaded':False,'simulation_advanced':False}
    m.original(w/'audit-v1.json',out);print(json.dumps(out))
