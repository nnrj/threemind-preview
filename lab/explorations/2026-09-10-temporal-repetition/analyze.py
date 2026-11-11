"""Evidence-only analysis. Never modifies Core, a checkpoint, or recorded windows."""
import io
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict

from run import HERE, WORK, META, Database, Settings, encoded, sha
from threemind_runtime.codec import ArtifactCodec

EPS = 1e-12

def order(nodes, field):
    rows = sorted([n for n in nodes if n.get(field) is not None], key=lambda n:(-n[field],n['node_id']))
    last, rank = None,0
    for i,n in enumerate(rows):
        if last is None or abs(n[field]-last)>EPS: rank=i+1
        n = dict(n,rank=rank)
        last=n[field]
        yield n

def scores(weights, channel_nodes):
    result = {}
    for term,mask in weights.items():
        found={int(c):w for c,w in mask.items() if int(c) in channel_nodes}
        complete=bool(mask) and len(found)==len(mask)
        result[term]=dict(channels=len(mask),observed_channels=len(found),complete=complete,
          value=(sum(w*channel_nodes[c]['last_activation'] for c,w in found.items())/sum(found.values())) if complete else None,
          peak=(sum(w*channel_nodes[c]['peak_activation'] for c,w in found.items())/sum(found.values())) if complete else None)
    return result

def outcome(values, expected):
    scalars={term:v['value'] for term,v in values.items()}
    if any(v is None for v in scalars.values()):
        return {'classification':'unmeasurable','winners':[],'expected':expected,'margin':None}
    best=max(scalars.values())
    winners=[term for term,v in scalars.items() if abs(v-best)<=EPS]
    return dict(classification='control_no_answer' if expected is None else 'tie' if len(winners)>1 else 'expected' if winners[0]==expected else 'other',
                winners=winners,expected=expected,
                margin=(scalars[expected]-max(v for term,v in scalars.items() if term!=expected)) if expected is not None else None)

def expected_answer(arm,group,cue):
    if group in ('family','seen_family') and len(cue)==1: return None
    if group=='pair':
        value={'甲':'松子','乙':'铃铛'}[cue]
    elif group=='who':
        value='甲' if '松子' in cue else '乙'
    elif group=='seen_family':
        return ('B' if '父亲' in cue else 'A') if cue.startswith('C') else ('E' if '父亲' in cue else 'D')
    else:
        if cue.startswith('Z'):
            return 'Y' if '父亲' in cue else 'U' if arm=='crossed' else 'X'
        return 'V' if '父亲' in cue else 'X' if arm=='crossed' else 'U'
    if arm=='swapped':
        return {'松子':'铃铛','铃铛':'松子','甲':'乙','乙':'甲'}[value]
    return value

def artifact_bytes(db,project,ident):
    with db.tx(project) as c:
        parts=c.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',(ident,)).fetchall()
    return b''.join(bytes(p['body']) for p in parts)

def analyze():
    meta=json.loads(META.read_bytes())
    db=Database(Settings.from_env().database_url)
    mappings={(m['seed'],m['group']):m['mapping'] for m in json.loads((HERE/'mapping.json').read_bytes())}
    cases,stages,fixed,resources=[],[],[],[]
    ranking_path=HERE/'node-rankings.jsonl'
    with ranking_path.open('w',encoding='utf-8') as rankings:
      try:
        for path in sorted(WORK.glob('seed-*-results.json')):
          study=json.loads(path.read_bytes())
          resources.append({k:v for k,v in study.items() if k!='rows'})
          for stage in study['rows']:
            cp,image=db.load_checkpoint(meta['project_id'],stage['run_id'],stage['checkpoint_id'])
            assert image.digest==stage['source_hash']
            state=image.to_dict()
            node_map={n['id']:n['channel'] for n in state['nodes']}
            edges=state['edges']
            stages.append({k:v for k,v in stage.items() if k!='measurements'} | {
                'mean_edge_weight':statistics.mean(e['weight'] for e in edges) if edges else None,
                'mean_edge_stability':statistics.mean(e['stability'] for e in edges) if edges else None,
                'unit_weight_fraction':sum(abs(e['weight']-1)<EPS for e in edges)/len(edges) if edges else None})
            for group_key,measure in stage['measurements'].items():
              result=json.loads((WORK/measure['file']).read_bytes())
              assert result['source_hash']==image.digest and result['source_unchanged']
              if measure['mode']=='fixed':
                fixed.append(dict(seed=stage['seed'],arm=stage['arm'],group=measure['group'],
                                  calibration_id=measure['id'],file=measure['file'],rows=result['rows']))
                continue
              raw=artifact_bytes(db,meta['project_id'],measure['artifacts']['bundle_artifact_id'])
              import hashlib
              assert hashlib.sha256(raw).hexdigest()==measure['artifacts']['bundle_sha256']
              with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for i,row in enumerate(result['rows']):
                  window=row['temporal']
                  base=dict(seed=stage['seed'],arm=stage['arm'],stage=stage['stage'],count=stage['count'],
                            group=measure['group'],role=('bare_name' if len(row['cue'])==1 else 'grandfather' if '爷爷' in row['cue'] else 'father') if measure['group'] in ('family','seen_family') else measure['group'],calibration_id=measure['id'],case_id=row['id'],
                            cue=row['cue'],dose=row['intensity'],classification=row['classification'],
                            reason=row['reason'],source_hash=result['source_hash'],context_inherited=row.get('context_inherited'))
                  if not window:
                    cases.append(base|{'converged':False,'nodes':0})
                    continue
                  final=ArtifactCodec.decode(archive.read(f'probes/{i}/final.tmind')).to_dict()
                  nm=node_map|{n['id']:n['channel'] for n in final['nodes']}
                  ranked=list(order(window['nodes'],'last_activation'))
                  channels={nm[n['node_id']]:n for n in window['nodes'] if n['node_id'] in nm}
                  mapping=mappings[(stage['seed'],measure['group'])]
                  full=scores(mapping['terms'],channels)
                  exclusive=scores(mapping['masks'],channels)
                  expected=expected_answer(stage['arm'],measure['group'],row['cue'])
                  last_values={str(n['node_id']):n['last_activation'] for n in window['nodes']}
                  base.update(window_id=window['window_id'],converged=row['classification']=='converged' and not window['censored'],
                    censored=window['censored'],duration_s=(int(window['end_us'])-int(window['start_us']))/1e6,
                    end_us=window['end_us'],nodes=len(ranked),candidate_count=window['candidate_count'],
                    active_at_end=sum(n['last_activation']>0 for n in ranked),
                    end_total=sum(last_values.values()),end_min=min(last_values.values(),default=None),
                    end_max=max(last_values.values(),default=None),distinct_end_values=len({round(v,12) for v in last_values.values()}),
                    unknown_node_channels=len(window['nodes'])-len(channels),
                    full_scores=full,exclusive_scores=exclusive,
                    full_outcome=outcome(full,expected),exclusive_outcome=outcome(exclusive,expected),
                    baseline_complete=window['coverage']['baseline_complete'],coverage=window['coverage'],
                    convergence=window['convergence'],overlapping_envelopes=window['overlapping_envelopes'],
                    top_end=[{'node_id':n['node_id'],'rank':n['rank'],'activation':n['last_activation'],
                              'channel':nm.get(n['node_id']),'candidate':n['candidate']} for n in ranked[:12]])
                  ranking_record=base|{'rankings':{
                    'end_activation':[dict(n,channel=nm.get(n['node_id'])) for n in ranked],
                    'peak_activation':[{'node_id':n['node_id'],'rank':n['rank'],'value':n['peak_activation']} for n in order(window['nodes'],'peak_activation')],
                    'existing_composite':window['candidate_ids']},'series':window['series']}
                  rankings.write(json.dumps(ranking_record,ensure_ascii=False,allow_nan=False)+'\n')
                  base['_vector']=last_values
                  cases.append(base)
      finally:
        db.close()
    index={(c['seed'],c['arm'],c['stage'],c['group'],c['cue'],c['dose']):c for c in cases}
    for c in cases:
        zero=index.get((c['seed'],c['arm'],c['stage'],c['group'],c['cue'],0.0))
        if c['dose'] and zero and '_vector' in c and '_vector' in zero:
            a,b=c['_vector'],zero['_vector']
            # No silent zero-fill: only shared sampled identities are compared.
            common=set(a)&set(b)
            c['zero_comparison']=dict(same_end_time=c['end_us']==zero['end_us'],shared_nodes=len(common),
                same_node_set=set(a)==set(b),max_abs_difference=max((abs(a[k]-b[k]) for k in common),default=None),
                changed_nodes=sum(abs(a[k]-b[k])>EPS for k in common))
    for c in cases: c.pop('_vector',None)
    groups=defaultdict(list)
    for c in cases: groups[(c['arm'],c['stage'],c['group'],c['role'],c['dose'])].append(c)
    summaries=[]
    for (arm,stage,group,role,dose),items in groups.items():
        summaries.append(dict(arm=arm,stage=stage,group=group,role=role,dose=dose,n=len(items),
          classifications=dict(Counter(c['classification'] for c in items)),
          full_outcomes=dict(Counter(c.get('full_outcome',{}).get('classification','unobserved') for c in items)),
          exclusive_outcomes=dict(Counter(c.get('exclusive_outcome',{}).get('classification','unobserved') for c in items)),
          all_full_outcomes_converged=dict(Counter(c.get('full_outcome',{}).get('classification','unobserved') for c in items if c['converged'])),
          exclusive_outcomes_converged=dict(Counter(c.get('exclusive_outcome',{}).get('classification','unobserved') for c in items if c['converged']))))
    result=dict(schema='threemind.temporal-repetition-analysis/1',unit='seed; within-seed windows are not independent replicates',
      primary='complete temporal window ending activation; ties retained; convergence status explicit',
      summaries=summaries,stages=stages,cases=cases,secondary_fixed=fixed,resources=resources,
      source_files={p.name:sha(p) for p in sorted(WORK.glob('*.json'))},analysis_sha256=sha(HERE/'analyze.py'))
    (HERE/'analysis.json').write_bytes(encoded(result))
    print(json.dumps({'seeds':len(resources),'cases':len(cases),'classifications':dict(Counter(c['classification'] for c in cases)),
                     'active_final_groups':[s for s in summaries if s['stage']=='final' and s['dose']==1]},ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    analyze()
