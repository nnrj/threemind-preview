"""Read-only independent trajectory, continuity, training and arithmetic audit."""
import argparse,json,math,random,statistics
from pathlib import Path
import numpy as np
import driver as d
from student import load,save,base,sha,FRAME_INDEX

def satisfied(c,a):return any(a[abs(x)-1]==(x>0) for x in c)
def good(f,a):return len(a)==f['n'] and all(satisfied(c,a) for c in f['clauses'])
def broken(f,a,v):
 b=a[:];b[v]=not b[v]
 return sum(satisfied(c,a) and not satisfied(c,b) for c in f['clauses'])
class InputChain:
 def __init__(self,state):
  self.h=state['input_digest'];self.n=state['input_count'];self.next=state['next_background'];self.t=int(state['core']['time_us']);self.mapping=state['mapping']
 def event(self,e):self.h=base.digest([self.h,e]);self.n+=1
 def advance(self,end):
  assert end>=self.t
  while self.next<=end:
   self.event(dict(time_us=self.next,channels=[[self.mapping['K'],.2]],intensity=1.));self.next+=500_000
  self.t=end
 def question(self,q):
  assert q['start_us']==self.t
  assert q['end_us']==self.t+1_000_000
  assert q['input']==dict(time_us=self.t,channels=[[self.mapping['C'+str(q['category'])],.8]],intensity=1.)
  self.event(q['input'])
  assert q['selected_indices']==FRAME_INDEX and len(q['frames'])==20
  for i,t in enumerate(q['frame_times_us']):
   assert t==q['start_us']+(i+1)*50_000 and len(q['frames'][i])==28
   assert all(math.isfinite(x) for x in q['frames'][i]);self.advance(t)
  assert q['prediction']==int(np.argmax(q['logits'])) and q['score']==int(q['prediction']==0)
 def lesson(self,r):
  self.advance(r['start_us'])
  for i,e in enumerate(r['events']):
   if i:self.advance(e['time_us'])
   assert e==dict(time_us=r['start_us']+i*250_000,channels=[[self.mapping['C'+str(r['category'])],.4],[self.mapping['P' if r['label']==0 else 'N'],.4]],intensity=1.)
   self.event(e)
  self.advance(r['end_us'])
 def verify(self,state):
  assert (self.h,self.n,self.next,self.t)==(state['input_digest'],state['input_count'],state['next_background'],int(state['core']['time_us']))

def audit_result(p,r,chain=None):
 a=r['initial_assignment'][:];local=[0,0];flips=0
 for st in r['steps']:
  assert not satisfied(p['clauses'][st['clause']],a)
  assert set(st['candidates'])=={abs(x)-1 for x in p['clauses'][st['clause']]}
  assert st['breaks']==[broken(p,a,v) for v in st['candidates']]
  if chain:
   for b,q in zip(st['breaks'],st['queries']):
    assert q['category']==min(b,3);chain.question(q)
    local[0]+=int(q['prediction']==int(b!=0));local[1]+=1
  v=st['candidates'][st['selected']];a[v]=not a[v]
  assert st['assignment']==a;flips+=1
 assert a==r['final_assignment'] and good(p,a)==r['solved']
 assert r['outcome']==('SAT' if r['solved'] else 'UNKNOWN') and flips==r['flips']
 if p.get('kind')=='unsatisfiable-sentinel':assert not r['solved']
 return local

def ci(values):
 a=np.array(values,dtype=float);rng=np.random.default_rng(2111199)
 samples=a[rng.integers(0,len(a),size=(50000,len(a)))].mean(axis=1)
 return dict(mean=float(a.mean()),per_origin=a.tolist(),ci95=np.quantile(samples,[.025,.975]).tolist(),ci975=np.quantile(samples,[.0125,.9875]).tolist())

def analyze(work):
 d.frozen(work)
 assert load(work/'status.json')['state']=='awaiting-analysis'
 assert not any((work/p).exists() for p in ('STOP','in-flight.json'))
 rows=[];training=[];transitions=0;queries=0;lessons=0;rule_equal={'normal':0,'shuffled':0}
 for o in range(8):
  m=load(work/f'material/o{o}.json')
  for arm in d.ARMS:
   folder=work/f'origins/o{o}/{arm}';assert load(folder/'done.json')['tests']==26
   state=None;chain=None
   if arm in ('normal','shuffled'):
    state=load(folder/'whole-birth.json.gz');chain=InputChain(state);config=state['core']['config']
    assert int(state['core']['time_us'])==0
    stages=sorted(folder.glob('fit-*.json'));assert 2<=len(stages)<=4
    previous_updates=0
    for j,fitpath in enumerate(stages):
     t=load(folder/f'teaching-{j}.json.gz');s=load(folder/f'samples-{j}.json.gz');v=load(folder/f'dev-{j}.json.gz');f=load(fitpath)
     assert t['added_review_delays_s']==[2,6,18] and t['dense_passes']==(10 if j==0 else 2)
     for r in t['lessons']:
      if arm=='normal':assert r['label']==int(r['category']!=0)
      chain.lesson(r);lessons+=1
     for r in s:
      assert r['label']==int(r['condition']['category']!=0);chain.question(r['question'])
     if j:
      old=load(folder/f'dev-{j-1}.json.gz')
      for error in old['errors']:assert any(r['condition']==error for r in s)
     for r in v['local_questions']:chain.question(r['question'])
     for p,result in zip(m['dev_problems'],v['sat_results']):audit_result(p,result,chain)
     updated=load(folder/f'whole-training-{j}.json.gz');chain.verify(updated)
     assert updated['core']['config']==config and updated['core']['life']!='dead'
     assert f['computed_updates']==f['committed_updates']==previous_updates+1200
     assert updated['learning_blocks']==j+1
     ref=updated['reader_ref']
     for name,h in ref['files'].items():assert sha(folder/ref['path']/name)==h
     previous_updates=f['committed_updates'];state=updated;transitions+=1
     gaps={}
     for c in range(4):
      ts=[x['start_us']/1e6 for x in t['lessons'] if x['category']==c]
      gaps[str(c)]={'count':len(ts),'start_seconds':ts,'interval_seconds':np.diff(ts).tolist()}
     training.append(dict(origin=o,arm=arm,cycle=j,local_correct=v['local_correct'],dev_sat=v['sat_solved'],ready=v['ready'],
          correction_errors=len(v['errors']),lesson_count=len(t['lessons']),samples=f['samples'],updates=f['committed_updates'],
          time_us=int(updated['core']['time_us']),spacing=gaps))
    fixed_ref=state['reader_ref'];fixed_digest=state['reader_digest']
   correct=nlocal=solved=flips=0;size={12:[0,0],20:[0,0]};all_solved=[];wall=0
   for i,p in enumerate(m['tests']):
    r=load(folder/f'result-{i:03d}.json.gz')
    if chain:
     assert r['before_sha256']==base.digest(state)
     rule=load(work/f'origins/o{o}/quantized-rule/result-{i:03d}.json.gz')
     common=lambda z:[(x['clause'],x['candidates'],x['selected'],x['assignment']) for x in z['steps']]
     rule_equal[arm]+=int(common(r)==common(rule))
    counts=audit_result(p,r,chain);correct+=counts[0];nlocal+=counts[1];queries+=counts[1]
    if chain:
     next_state=load(folder/f'whole-test-{i+1:03d}.json.gz')
     assert r['after_sha256']==base.digest(next_state)
     chain.verify(next_state);assert next_state['reader_ref']==fixed_ref and next_state['reader_digest']==fixed_digest
     assert next_state['core']['config']==config and next_state['core']['life']!='dead'
     assert next_state['sample_refs']==state['sample_refs'];state=next_state;transitions+=1
    if p['kind']=='satisfiable':
     solved+=r['solved'];flips+=r['flips'];wall+=r['wall_seconds'];size[p['n']][0]+=r['solved'];size[p['n']][1]+=1
    all_solved.append(bool(r['solved']))
   rows.append(dict(origin=o,arm=arm,solved=solved,n=24,flips=flips,solved_by_size={str(k):v for k,v in size.items()},
      local_correct=correct,local_n=nlocal,local_accuracy=correct/nlocal if nlocal else None,
      final_internal_us=int(state['core']['time_us']) if chain else None,final_reader_updates=previous_updates if chain else None,
      final_wall_seconds=wall,all_solved=all_solved))
 totals={a:dict(solved=sum(r['solved'] for r in rows if r['arm']==a),n=192,
                local_correct=sum(r['local_correct'] for r in rows if r['arm']==a),local_n=sum(r['local_n'] for r in rows if r['arm']==a),
                flips=sum(r['flips'] for r in rows if r['arm']==a),wall_seconds=sum(r['final_wall_seconds'] for r in rows if r['arm']==a)) for a in d.ARMS}
 paired={}
 for a in ('random-local','shuffled','quantized-rule','walksat'):
  x=[(next(r['solved'] for r in rows if r['origin']==o and r['arm']=='normal')-next(r['solved'] for r in rows if r['origin']==o and r['arm']==a))/24 for o in range(8)]
  paired[a]=ci(x)
 g1=paired['random-local']['mean']>=.1 and paired['random-local']['ci975'][0]>0
 g2=paired['shuffled']['mean']>=.1 and paired['shuffled']['ci975'][0]>0
 result=dict(schema='sat-curriculum-analysis/1',independent_origins=8,students=16,totals=totals,paired=paired,per_origin=rows,
    training=training,gates=dict(G1=bool(g1),G2=bool(g2),G3=True),
    audit=dict(witnesses_and_trajectories=8*5*26,whole_transitions=transitions,final_temporal_queries=queries,lessons=lessons,
      complete_input_chains=True,trajectory_equal_to_quantized_rule=rule_equal,trajectory_equal_denominator=208,core_parameters_unchanged=True,final_readers_frozen=True,original_error_conditions_resampled=True),
    resource=load(work/'resource-summary.json'))
 save(work/'analysis-v2.json',result)
 small={k:result[k] for k in ('schema','independent_origins','students','totals','paired','gates','audit','resource')}
 (d.HERE/'summary.json').write_text(json.dumps(small,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(small,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=d.WORK);a=p.parse_args();analyze(a.work.resolve())
