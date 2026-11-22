"""Pure, preregistered E43 measurements; no engine or decoder is constructed."""
import hashlib
import math

WORDS=('松子','铃铛','陶杯','柳叶')
CONDITIONS=('spaced','reversed','massed','frozen','untaught')


def classify(text):
    matches=[word for word in WORDS if word in (text or '')]
    return matches[0] if len(matches)==1 else None


def structure(graph,seed):
    """Use a same-time graph projection, not stale stored lazy-update weights."""
    mask=int.from_bytes(hashlib.blake2s(f'language-input/1:{seed}'.encode(),digest_size=4).digest(),'big')
    nodes={str(n['id']):n for n in graph['nodes']}
    origin={identity:('language' if 0 <= (int(node['channel'])^mask) < 128 else 'background')
            for identity,node in nodes.items()}
    groups={a+'-to-'+b:[] for a in ('language','background') for b in ('language','background')}
    for edge in graph['edges']:
        assert str(edge['source']) in nodes and str(edge['target']) in nodes
        value=float(edge['weight']);assert math.isfinite(value) and value>=0
        groups[origin[str(edge['source'])]+'-to-'+origin[str(edge['target'])]].append(value)
    return {'nodes':{kind:sum(v==kind for v in origin.values()) for kind in ('language','background')},
        'edges':{kind:{'count':len(values),'weights':sorted(values),
            'mean_weight':math.fsum(values)/len(values) if values else 0.,
            'max_weight':max(values,default=0.)} for kind,values in groups.items()}}


def retention_decisions(rows):
    index={(v['seed'],v['condition'],v['seconds']):v for v in rows}
    assert len(index)==len(rows)
    blocks=[]
    for seed in (17,29):
        points=[]
        for seconds in (530,830):
            values={condition:index[seed,condition,seconds]['edges']['language-to-language']
                    for condition in CONDITIONS}
            normal=values['spaced'];massed=values['massed']
            points.append({'seconds':seconds,'conditions':values,
                'spaced_connections_present':normal['count']>0,
                'spaced_weight_above_massed':normal['max_weight']>massed['max_weight'],
                'spaced_count_above_massed':normal['count']>massed['count'],
                'spaced_weight_above_untaught':normal['max_weight']>values['untaught']['max_weight'],
                'spaced_weight_above_frozen':normal['max_weight']>values['frozen']['max_weight']})
        blocks.append({'seed':seed,'points':points,
            'weight_advantage_both_times':all(v['spaced_weight_above_massed'] for v in points),
            'count_advantage_at_300s':points[1]['spaced_count_above_massed'],
            'ordinary_retention_present':all(v['spaced_connections_present'] for v in points)})
    return {'blocks':blocks,
        'weight_advantage_replicated':all(v['weight_advantage_both_times'] for v in blocks),
        'count_advantage_replicated':all(v['count_advantage_at_300s'] for v in blocks),
        'scientific_stop':not all(v['ordinary_retention_present'] for v in blocks)}


def transmission(result):
    """Completed emission after connection gates, during this diagnostic only.

    This is the existing sent-minus-discarded metric, summed across signal
    types. It measures emitted quantity, not delivery or postsynaptic activity.
    """
    before=result['initial_metrics']['transport'];after=result['metrics']['transport']
    differences={key:float(after.get(key,0))-float(before.get(key,0)) for key in ('sent','discarded')}
    assert min(differences.values())>=-1e-9
    passed=math.fsum((differences['sent'],-differences['discarded']))
    assert passed>=-1e-9
    return {'sent':differences['sent'],'discarded':differences['discarded'],'passed':passed}


def language_scores(cases,texts):
    """One unique target word per response; paired history success is conjunctive."""
    rows=[]
    for case in cases:
        if case['kind']!='probe' or case['probe'] is None:continue
        text=texts[case['key'],1]
        prediction=classify(text)
        rows.append({k:case[k] for k in ('key','source','seed','condition','checkpoint','cue_index',
            'probe','label','probe_intensity','historical_kind')}|
            {'text':text,'prediction':prediction,'correct':prediction==case['label']})
    assert len(rows)==440
    index={(v['seed'],v['condition'],v['checkpoint'],v['cue_index']):v for v in rows
           if v['historical_kind']=='probe'}
    assert len(index)==400
    paired=[]
    for seed in (17,29):
        for seconds in (24,144,530,590,830):
            pairs=[]
            for cue in range(8):
                normal=index[seed,'spaced',seconds,cue];reverse=index[seed,'reversed',seconds,cue]
                assert normal['probe']==reverse['probe'] and normal['label']!=reverse['label']
                pairs.append({'cue_index':cue,'normal_correct':normal['correct'],
                    'reversed_correct':reverse['correct'],'passed':normal['correct'] and reverse['correct']})
            paired.append({'seed':seed,'seconds':seconds,'passed':sum(v['passed'] for v in pairs),
                'denominator':8,'pairs':pairs})
    return {'primary_window':1,'primary_rows':[v for v in rows if v['historical_kind']=='probe'],
        'dose_rows':[v for v in rows if v['historical_kind']=='probe-dose'],'paired':paired}
