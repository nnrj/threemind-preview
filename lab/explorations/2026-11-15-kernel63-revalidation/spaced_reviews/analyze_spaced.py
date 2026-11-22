"""Read-only lineage, stimulus, process-feature, structural and answer audit."""
import argparse
from collections import Counter
import copy
import json
import lzma
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_spaced as r
e=r.e;mat=r.mat;read=r.read;m=r.measure


def normalize_stimulus(value):
    return e.base.Stimulus.from_dict(value).to_dict()


def compare_inputs(case,source,assets,background,first,last,delivered,scheduled):
    expected=[]
    for index in range(first['background_cursor'],last['background_cursor']):
        row=background[index]
        if row['stimulus']:
            v=normalize_stimulus(row['stimulus']);v['time_us']=str(row['time_us'])
            expected.append(('recorded-physical-'+row['scope'],v))
    if case['kind']=='teach':
        for lesson in source['lessons'][first['lesson_cursor']:last['lesson_cursor']]:
            v=e.embedding_frame(assets['vectors'][lesson['text']],mat.protocol(case['seed']),1.).to_dict()
            v['time_us']=str(lesson['time_us']);expected.append(('ordinary-spaced-language',v))
    elif case['probe'] is not None:
        v=e.embedding_frame(assets['vectors'][case['probe']],mat.protocol(case['seed']),case['probe_intensity']).to_dict()
        v['time_us']=str(case['begin_us']);expected.append(('manual-language-adapter',v))
    assert len(expected)==len(delivered)==len(scheduled)
    index={v['receipt']['core_event_id']:v for v in scheduled};assert len(index)==len(scheduled)
    # Match source and timestamp first, then verify exact encoded input, including any declared attention selection.
    grouped={}
    for source_name,v in expected:grouped.setdefault((source_name,str(v['time_us'])),[]).append(v)
    for entry in delivered:
        assert not entry.get('labels') and entry['core_event_id'] in index
        assert entry['scheduled_time_us']==entry['delivered_time_us']==entry['stimulus']['time_us']
        at=int(entry['scheduled_time_us']);assert case['begin_us']<=at<case['end_us']
        assert case['begin_us']<=index[entry['core_event_id']]['enqueue_us']<=at
        choices=grouped[entry['source'],entry['scheduled_time_us']]
        matched=[]
        for n,raw in enumerate(choices):
            value=copy.deepcopy(raw);value['bypass_attention']=entry['source_policy']['bypass_attention']
            gate=entry.get('input_gate')
            if gate:
                channels=value['channels'];limit=gate['effective_budget']
                if gate['gain']==0:channels=[]
                elif not value['bypass_attention'] and limit is not None and limit<len(channels):
                    selected=set(sorted(range(len(channels)),key=lambda i:(-channels[i][1],i))[:limit])
                    channels=[v for i,v in enumerate(channels) if i in selected]
                value['channels']=channels;value['intensity']*=gate['gain']
            if normalize_stimulus(value)==normalize_stimulus(entry['stimulus']):matched.append(n)
        assert matched,'delivered input differs from frozen curriculum'
        choices.pop(matched[0])
    assert not any(grouped.values())
    return len(delivered)


def projected_weights(state,graph):
    cfg=state['config'];assert cfg['consolidation_mode']=='adaptive-half-life'
    assert cfg['decay_curve']=='inverse-logarithmic' and not cfg['retention_relaxation_enabled']
    raw={(int(v['source']),int(v['target'])):v for v in state['edges']}
    assert len(raw)==len(graph['edges'])
    maximum=0.
    for edge in graph['edges']:
        v=raw[int(edge['source']),int(edge['target'])]
        expected=v['weight']
        if cfg['plasticity']:
            age=v['decay_age'];delta=(int(state['time_us'])-int(v['state_us']))/1e6/v['half_life']
            expected*=(1+math.log1p(math.expm1(1)*age))/(1+math.log1p(math.expm1(1)*(age+delta)))
        maximum=max(maximum,abs(edge['weight']-expected))
    assert maximum<1e-12
    return maximum


def analyze(work):
    r.check(work);summary=read(work/'summary.json');decoded=read(work/'decoding-summary.json')
    assert summary['stages']==580 and decoded['windows']==640 and not (work/'in-flight.json').exists()
    cases=read(work/'cases.json');sources={v['key']:v for v in read(work/'inventory.json')['sources']}
    assets,background=r.inputs(work);counts=Counter();structure=[];transmissions=[]
    feature_error=0.;weight_error=0.;costs=[]
    for number,case in enumerate(cases,1):
        folder=work/'cases'/case['key'];result=read(folder/'result.json');source=sources[case['source']]
        assert result['key']==case['key'] and result['kernel']==e.KERNEL and not result['calibration']
        assert result['status']=='complete' and result['mode']=='observed' and result['life']=='active'
        if case['parent']:
            parent=e.base.image(work/'cases'/case['parent']/'final.tmind')
            reference=read(folder/'initial-reference.json')
            assert parent.digest==result['parent_sha256']==result['initial_sha256']==reference['sha256']
            assert reference['parent']==case['parent'];initial=parent
        else:initial=e.base.image(folder/'initial.tmind')
        final=e.base.image(folder/'final.tmind');a,z=initial.to_dict(),final.to_dict()
        assert initial.digest==result['initial_sha256'] and final.digest==result['final_sha256']
        for state in (a,z):
            cfg=state['config'];assert state['dynamics']==e.KERNEL
            assert cfg['seed']==mat.CORE_SEED and cfg['plasticity']==(case['condition']!='frozen')
            assert cfg['signal_threshold']==.0004 and cfg['prune_weight']==.008
            assert cfg['inhibition_updates_usage'] and not cfg['resource_precheck_enabled']
            assert not cfg['inhibition_bypasses_resources'] and not cfg['separate_inhibition_resources']
            assert cfg['subthreshold_expiry_enabled'] and all(n['id']==n['channel'] for n in state['nodes'])
        assert a['config']==z['config'] and int(a['time_us'])==case['begin_us'] and int(z['time_us'])==case['end_us']
        first=e.unpacked(folder/'initial-whole.json.xz');last=e.unpacked(folder/'whole.json.xz')
        if case['parent']:assert first==e.unpacked(work/'cases'/case['parent']/'whole.json.xz')
        assert first['language']['protocol']==last['language']['protocol']==mat.protocol(case['seed']).model_dump()
        assert not last['language']['readouts']['input_bus']['pending']
        assert last['background_cursor']>=first['background_cursor']
        assert last['lesson_cursor']>=first['lesson_cursor']
        if case['kind']=='probe':assert last['lesson_cursor']==first['lesson_cursor']
        delivered=e.unpacked(folder/'delivered.json.xz');scheduled=e.unpacked(folder/'scheduled.json.xz')
        inputs=compare_inputs(case,source,assets,background,first,last,delivered,scheduled)
        assert inputs==result['inputs'];counts['inputs']+=inputs
        with lzma.open(folder/'trajectory.jsonl.xz','rt',encoding='utf-8') as stream:
            if case['kind']=='probe':
                rows=[json.loads(line) for line in stream];assert len(rows)==4
                for index,row in enumerate(rows):
                    process=row['process'];values,bins=r.feature.features(process,case['seed'])
                    assert bins==process['samples_per_bin'] and row['window']==index
                    assert row['features']==process['features']==result['windows'][index]['features']
                    feature_error=max(feature_error,max(abs(x-y) for x,y in zip(values,row['features'],strict=True)))
                    assert feature_error<1e-12
                    assert int(process['start_us'])==case['begin_us']+index*500000
                    assert int(process['planned_end_us'])==case['begin_us']+(index+1)*500000
                    counts['process_windows']+=1
            else:
                last_time=case['begin_us']
                for line in stream:
                    point=json.loads(line);assert point['time_us']>last_time
                    last_time=point['time_us'];counts['teaching_observations']+=1
                assert last_time==case['end_us']
        with lzma.open(folder/'four-field.jsonl.xz','rt',encoding='utf-8') as stream:
            extra=[json.loads(line) for line in stream]
        if case['kind']=='probe':
            assert len(extra)==4
            for index,row in enumerate(extra):
                assert row['window']==index
                points=row['points'];begin=case['begin_us']+index*500000
                expected=list(range(begin,begin+500000,mat.protocol(case['seed']).sample_us))+[begin+500000]
                assert [p['time_us'] for p in points]==expected
                assert all(all(k in n for k in e.FIELDS) for p in points for n in p['nodes'])
            transmissions.append({'key':case['key'],'seed':case['seed'],'condition':case['condition'],
                'checkpoint':case['checkpoint'],'cue_index':case['cue_index'],**m.transmission(result)})
        else:
            graph=e.unpacked(folder/'projection.json.xz');weight_error=max(weight_error,projected_weights(z,graph))
            structure.append({'source':case['source'],'seed':case['seed'],'condition':case['condition'],
                'seconds':case['end_us']//1000000,**m.structure(graph,case['seed'])})
        counts['stages']+=1;counts[case['kind']]+=1;counts['complete_states']+=1+int(case['parent'] is None)
        cost=read(work/'costs'/f'{number:03d}.json');actual=r.evidence_cost(folder,case)
        assert cost['unit']==case['key'] and all(cost[k]==v for k,v in actual.items());costs.append(cost)
        if number%40==0:print('audited',number,'/580',flush=True)
    assert counts['teach']==90 and counts['probe']==490 and counts['process_windows']==1960
    assert counts['complete_states']==590
    texts={(v['key'],v['window']):v['text'] for v in decoded['answers']};assert len(texts)==640
    requests={}
    for case in cases:
        if case['kind']=='probe':
            result=read(work/'cases'/case['key']/'result.json')
            for index in ((0,1,2,3) if case['probe'] is None else (1,)):
                requests.setdefault(case['seed'],[]).append((case['key'],index,result['windows'][index]['features']))
    verified=0
    for batch in decoded['batches']:
        folder=work/batch['folder'];seed,offset=map(int,folder.name.split('-'));result=read(folder/'result.json')
        chunk=requests[seed][offset:offset+96];payload=read(folder/'payload.json')
        assert set(payload)=={'protocol','windows'} and payload['protocol']==mat.protocol(seed).model_dump()
        assert payload['windows']==[v[2] for v in chunk] and result['created_engines']==0
        assert result['head_sha256']==mat.sha(work/'materials'/f'head-{seed}.safetensors')
        assert len(result['windows'])==len(chunk)
        for (key,index,_),answer in zip(chunk,result['windows'],strict=True):
            assert answer['text']==texts[key,index]
        verified+=len(chunk)
    assert verified==640
    language=m.language_scores(cases,texts)
    retention=m.retention_decisions([v for v in structure if v['seconds'] in (530,830)])
    analysis={'kernel':e.KERNEL,'material_blocks':2,'teaching_individuals':10,'diagnostic_copies':490,
        'counts':dict(counts),'structure':structure,'retention':retention,'language':language,
        'transmission':transmissions,'maximum_feature_error':feature_error,'maximum_projection_weight_error':weight_error,
        'core_wall_seconds':summary['wall_seconds'],'decode_wall_seconds':decoded['wall_seconds']}
    r.s.base.original(work/'analysis.json',analysis)
    audit={'passed':True,'read_only':True,'created_engines':0,'loaded_decoders':0,'counts':dict(counts),
        'decoded_windows_verified':verified,'scientific_stop':retention['scientific_stop'],
        'maximum_feature_error':feature_error,'maximum_projection_weight_error':weight_error}
    r.s.base.original(work/'audit.json',audit);print(json.dumps(audit),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    analyze(parser.parse_args().work.resolve())
