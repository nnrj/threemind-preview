"""Read-only arithmetic, full trajectory, whole-state and reader replay verification."""
import argparse,importlib.util,json,math,random
from pathlib import Path
import numpy as np
import torch
import study as d
spec=importlib.util.spec_from_file_location('v2_input_audit',d.V2/'analyze.py');v2audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2audit)
def valid(clauses,a):return all(any(a[abs(x)-1]==(x>0) for x in c) for c in clauses)
def broken(clauses,a,v):
 b=a[:];b[v]=not b[v]
 return sum(any(a[abs(x)-1]==(x>0) for x in c) and not any(b[abs(x)-1]==(x>0) for x in c) for c in clauses)
def confidence(x,level=.9):
 x=np.asarray(x,float);rng=np.random.default_rng(3111299);means=x[rng.integers(0,len(x),size=(50000,len(x)))].mean(1)
 lo,hi=np.quantile(means,[(1-level)/2,1-(1-level)/2]);return dict(mean=float(x.mean()),interval=[float(lo),float(hi)],level=level,per_origin=x.tolist())
def audit(work):
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
 d.frozen(work);assert d.load(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
 assert not any((work/n).exists() for n in ('STOP','in-flight.json'))
 rows=[];replays=0;transitions=0;restored_equal=0;max_logit_error=0.;all_static_tables={};fresh_initial_tables={};calibration_predictions=0
 for o in range(8):
  m=d.load(work/f'material/o{o}.json');parent=d.load(work/f'parents/o{o}/whole-test-026.json.gz')
  templates=d.load(work/f'templates/o{o}.json.gz')
  for t in templates.values():
   assert int(t['before']['core']['time_us'])==0 and t['before']['input_count']==0 and t['before']['learning_blocks']==0 and not t['before']['lesson_times']
  for arm in d.ARMS:
   folder=work/f'origins/o{o}/{arm}';assert d.load(folder/'done.json')['tests']==26
   local_correct=0;local_n=0;probe_correct=None;query_n=0;solved=flips=0;wall=0;trajectory_equal=0;outputs=[];fixed_ref=None;reader=None;old_state=None;input_chain=None;probe_frame_max_difference=None;probe_prediction_equal=None
   if arm in d.ARMS[:8]:
    birth=d.load(folder/'whole-start.json.gz')
    for rel,h in birth['reader_ref']['files'].items():assert d.sha(folder/birth['reader_ref']['path']/rel)==h
    if arm in d.TRAINED:
     assert int(d.load(folder/birth['reader_ref']['path']/'manifest.json')['committed_updates'])==0
     initial_reader=d.CalibratedActivity.restore(folder/birth['reader_ref']['path'])
     raw={}
     for c in range(4):
      x=np.zeros((20,7,4),dtype=np.float32)
      if arm=='relay-trained':
       for symbol,strength in (('C'+str(c),.8),('K',.2)):
        pos=initial_reader.layout.index[parent['mapping'][symbol]];x[:,pos,0]=strength;x[:,pos,2]=strength
      raw[c]=x.reshape(20,28).tolist()
     initial_logits=initial_reader.predict([[raw[c][i] for i in d.FRAME_INDEX] for c in range(4)])
     fresh_initial_tables[f'o{o}/{arm}']={str(c):int(np.argmax(initial_logits[c])) for c in range(4)}
     calibration_chain=birth['chain'];calibration_count=0;calibration_clock=0
     for j in range(4):
      fit=d.load(folder/f'fit-{j}.json');assert fit['receipt']['computed_updates']==fit['receipt']['committed_updates']==(j+1)*1200
      state=d.load(folder/f'whole-fit-{j}.json.gz');assert state['student'] is None and len(state['samples'])==j+1
      sample=d.load(folder/f'samples-{j}.json.gz');assert len(sample)==48
      original_samples=d.load(work/f'parents/o{o}'/parent['sample_refs'][j])
      assert all(r['label']==int(r['condition']['category']!=0) and r['condition']==orig['condition'] and r['frames']==raw[r['condition']['category']] for r,orig in zip(sample,original_samples))
      for name,h in state['reader_ref']['files'].items():assert d.sha(folder/state['reader_ref']['path']/name)==h
      fit_reader=d.CalibratedActivity.restore(folder/state['reader_ref']['path'])
      cats=list(range(4))*4;assert [q['category'] for q in fit['development']]==cats
      logits=fit_reader.predict([[raw[c][i] for i in d.FRAME_INDEX] for c in cats])
      for q,values in zip(fit['development'],logits):
       assert int(np.argmax(values))==q['prediction'];calibration_predictions+=1
       calibration_chain=d.base.digest([calibration_chain,dict(category=q['category'],start_us=calibration_clock,end_us=calibration_clock+1_000_000,prediction=q['prediction'])])
       calibration_count+=1;calibration_clock+=1_000_000
      assert state['chain']==calibration_chain and state['count']==calibration_count and state['clock']==calibration_clock
     pre=d.load(folder/'whole-fit-3.json.gz')
    else:
     pre=birth;assert pre['reader_ref']['digest']==parent['reader_digest']
    fixed_ref=pre['reader_ref'];reader=d.CalibratedActivity.restore(folder/fixed_ref['path'])
    expected_chain=pre['chain'];expected_count=pre['count'];expected_time=int(pre['student']['core']['time_us']) if pre['student'] else pre['clock']
    if pre['student']:input_chain=v2audit.InputChain(pre['student'])
    def check_questions(qs):
     nonlocal replays,expected_chain,expected_count,expected_time,max_logit_error,query_n
     if not qs:return
     for q in qs:
      c=q['category'];assert type(c)is int and c in range(4)
      assert q['start_us']==expected_time and q['end_us']==expected_time+1_000_000
      expected_time=q['end_us'];assert q['selected_indices']==d.FRAME_INDEX
      assert q['frame_times_us']==[q['start_us']+(i+1)*50_000 for i in range(20)]
      assert len(q['frames'])==20 and all(len(x)==28 and all(math.isfinite(v) for v in x) for x in q['frames'])
      if input_chain:input_chain.question(q)
      elif arm=='template-fixed':assert q['frames']==templates[str(parent['mapping']['C'+str(c)])]['frames']
      else:
       expected=np.zeros((20,7,4),dtype=np.float32)
       if not arm.startswith('constant'):
        for name,strength in (('C'+str(c),.8),('K',.2)):
         idx=reader.layout.index[parent['mapping'][name]];expected[:,idx,0]=strength;expected[:,idx,2]=strength
       assert q['frames']==expected.reshape(20,28).tolist()
      assert q['prediction']==int(np.argmax(q['logits'])) and q['score']==int(q['prediction']==0)
      expected_count+=1;expected_chain=d.base.digest([expected_chain,{'category':c,'start_us':q['start_us'],'end_us':q['end_us'],'prediction':q['prediction']}])
     for offset in range(0,len(qs),128):
      part=qs[offset:offset+128];pred=reader.predict([[q['frames'][i] for i in d.FRAME_INDEX] for q in part])
      for r,q in zip(pred,part):
       assert int(np.argmax(r))==q['prediction'];err=float(np.max(np.abs(r-np.array(q['logits']))));max_logit_error=max(max_logit_error,err)
       assert err<1e-4;replays+=1
     query_n+=len(qs)
    def check_state(path):
     nonlocal old_state,transitions
     s=d.load(path);assert s['parent_sha']==birth['parent_sha'] and s['mode']==arm and s['reader_ref']==fixed_ref
     assert s['chain']==expected_chain and s['count']==expected_count
     if s['student']:
      assert s['student']['core']['config']==parent['core']['config'];input_chain.verify(s['student'])
      assert s['student']['reader_digest']==fixed_ref['digest']
      for rel in s['student']['sample_refs']:assert (folder/rel).is_file()
     else:assert s['clock']==expected_time
     for n,h in fixed_ref['files'].items():assert d.sha(folder/fixed_ref['path']/n)==h
     if arm=='restored':assert s['student']==d.load(work/f'origins/o{o}/intact'/path.name)['student']
     old_state=path;transitions+=1
     return s
    probes=d.load(folder/'probes.json.gz');assert [q['category'] for q in probes]==m['probes']
    check_questions(probes);probe_correct=sum(q['prediction']==int(q['category']!=0) for q in probes)
    check_state(folder/'whole-probes.json.gz')
    reference_probes=d.load(work/f'origins/o{o}/intact/probes.json.gz')
    probe_frame_max_difference=float(np.max(np.abs(np.asarray([q['frames'] for q in probes])-np.asarray([q['frames'] for q in reference_probes]))))
    probe_prediction_equal=sum(q['prediction']==r['prediction'] for q,r in zip(probes,reference_probes))
    if arm=='blank-core':
     assert int(birth['student']['core']['time_us'])==0 and int(parent['core']['time_us'])>0
     assert birth['student']['core']!=parent['core'] and birth['student']['input_count']==0
    if arm=='restored':assert probes==d.load(work/f'origins/o{o}/intact/probes.json.gz')
    if arm not in d.LIVE:
     table={str(c):sorted(set(q['prediction'] for q in probes if q['category']==c)) for c in range(4)}
     assert all(len(v)==1 for v in table.values());all_static_tables[f'o{o}/{arm}']=table
   for j,p in enumerate(m['tests']):
    r=d.load(folder/f'result-{j:03d}.json.gz');a=r['initial_assignment'][:]
    rng=random.Random(p['rng_seed']);expected_initial=[bool(rng.getrandbits(1)) for _ in range(p['n'])]
    assert a==expected_initial and len(a)==p['n'] and all(type(x)is bool for x in a)
    if reader:assert r['before_checkpoint_sha256']==d.sha(old_state)
    qs=[]
    for k,st in enumerate(r['steps']):
     assert st['step']==k and not any(a[abs(x)-1]==(x>0) for x in p['clauses'][st['clause']])
     assert set(st['candidates'])=={abs(x)-1 for x in p['clauses'][st['clause']]}
     bs=[broken(p['clauses'],a,v) for v in st['candidates']];assert bs==st['breaks']
     bad=[i for i,c in enumerate(p['clauses']) if not any(a[abs(x)-1]==(x>0) for x in c)]
     ci=rng.choice(bad);vs=[abs(x)-1 for x in p['clauses'][ci]];rng.shuffle(vs)
     assert ci==st['clause'] and vs==st['candidates']
     if arm=='walksat' and 0 in bs:pick=rng.choice([i for i,b in enumerate(bs) if b==0]);noise=False
     elif arm=='random-local':pick=rng.randrange(3);noise=True
     else:
      scores=[q['score'] for q in st['queries']] if reader else [int(b==0) for b in bs] if arm=='quantized-rule' else [-b for b in bs]
      noise=rng.random()<(.5 if arm=='walksat' else .25)
      pick=rng.randrange(3) if noise else rng.choice([i for i,x in enumerate(scores) if abs(x-max(scores))<=1e-12])
     assert pick==st['selected'] and noise==st['noise']
     if reader:
      assert [q['category'] for q in st['queries']]==[min(b,3) for b in bs]
      qs.extend(st['queries']);local_correct+=sum(q['prediction']==int(b!=0) for q,b in zip(st['queries'],bs));local_n+=3
     a[st['candidates'][st['selected']]]=not a[st['candidates'][st['selected']]];assert a==st['assignment']
    assert a==r['final_assignment'] and valid(p['clauses'],a)==r['solved']
    assert r['flips']==len(r['steps'])<=96 and r['outcome']==('SAT' if r['solved'] else 'UNKNOWN')
    if p['kind']=='unsatisfiable-sentinel':assert r['outcome']=='UNKNOWN'
    if reader:
     check_questions(qs);saved=check_state(folder/f'whole-test-{j+1:03d}.json.gz')
     assert r['steps'], 'Registered material audit expected a nonempty action sequence'
     expected_world=dict(problem_id=p['id'],assignment=a,environment_rng=json.loads(d.base.encoded(rng.getstate())),step=len(r['steps']))
     assert saved['world']==expected_world
     if saved['student']:
      assert saved['student']['world']==expected_world and saved['student']['body']['state']==expected_world
      assert saved['student']['actuator']==dict(type='one-bit-flip',noise=.25)
    reference=d.load(work/f'origins/o{o}/intact/result-{j:03d}.json.gz')
    sig=lambda z:[(x['clause'],x['candidates'],x['selected'],x['assignment']) for x in z['steps']]
    equal=sig(r)==sig(reference);trajectory_equal+=equal
    if arm=='restored':assert r['steps']==reference['steps'];restored_equal+=1
    if p['kind']=='satisfiable':solved+=r['solved'];flips+=r['flips'];wall+=r['wall_seconds']
    outputs.append(bool(r['solved']))
   rows.append(dict(origin=o,arm=arm,solved=solved,n=24,flips=flips,wall_seconds=wall,probe_correct=probe_correct,probe_n=64 if reader else 0,
       local_correct=local_correct,local_n=local_n,trajectory_equal=trajectory_equal,trajectory_n=26,query_n=query_n,probe_frame_max_difference=probe_frame_max_difference,probe_prediction_equal=probe_prediction_equal,outcomes=outputs))
  print(json.dumps(dict(audited_origin=o)),flush=True)
 totals={arm:{k:sum(r[k] or 0 for r in rows if r['arm']==arm) for k in ('solved','n','flips','wall_seconds','probe_correct','probe_n','local_correct','local_n','trajectory_equal','trajectory_n','query_n')} for arm in d.ARMS}
 paired={};targets={}
 def per(arm,k):return np.array([next(r[k] for r in rows if r['origin']==o and r['arm']==arm) for o in range(8)])
 for arm in ('blank-core','relay-fixed','template-fixed','relay-trained'):
  interval=confidence((per(arm,'solved')-per('intact','solved'))/24)
  accuracy=float(np.mean((per(arm,'probe_correct')-per('intact','probe_correct'))/64))
  eq=interval['interval'][0]>-.05 and interval['interval'][1]<.05 and accuracy>=-.01
  if arm=='relay-trained':eq=eq and all(all(v==[int(c!='0')] for c,v in table.items()) for key,table in all_static_tables.items() if key.endswith('/relay-trained'))
  paired[arm]=interval|dict(local_accuracy_difference=accuracy);targets[arm]=bool(eq)
 for arm,ref in (('constant-fixed','relay-fixed'),('constant-trained','relay-trained')):
  interval=confidence((per(ref,'solved')-per(arm,'solved'))/24,.95)
  drop=float(np.mean((per(ref,'probe_correct')-per(arm,'probe_correct'))/64))
  paired[arm]=interval|dict(local_accuracy_drop=drop,reference=ref);targets[arm]=bool(drop>=.25 and interval['interval'][0]>0)
 result=dict(schema='sat-core-exclusion-analysis/1',independent_origins=8,totals=totals,paired=paired,targets=targets,per_origin=rows,static_category_tables=all_static_tables,fresh_initial_category_tables=fresh_initial_tables,
  audit=dict(witness_trajectories=8*len(d.ARMS)*26,whole_transitions=transitions,reader_predictions_replayed=replays,calibration_predictions_replayed=calibration_predictions,max_logit_replay_error=max_logit_error,restored_identical_trajectories=restored_equal,parents_unchanged=True,fixed_readers_unchanged=True),resource=d.load(work/'resource-summary.json'))
 d.save(work/'analysis-v1.json',result)
 (d.HERE/'summary.json').write_text(json.dumps({k:v for k,v in result.items() if k not in ('per_origin','static_category_tables','fresh_initial_category_tables')},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'targets':targets,'scores':{a:t['solved'] for a,t in totals.items()},'audit':result['audit']},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=d.WORK);a=p.parse_args();audit(a.work.resolve())