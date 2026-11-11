"""Isolated apparatus: continuity, temporal input, teaching and truth isolation."""
import copy,json,random,time,unittest
from pathlib import Path
import numpy as np
import torch
from student import Student,base,load,save,sha,make_material,balanced_cases,FRAME_INDEX,tensor_hash
import driver as d
ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'.work'/('sat-curriculum-validation-'+str(time.time_ns()))
RUN.mkdir(parents=True)
MEASURE={}
class Apparatus(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
  cls.started=time.perf_counter();cls.m=make_material(2111000)
  cls.s=Student(2111000,'apparatus-only')
  cls.teaching=cls.s.curriculum(cls.m['examples'],'normal','initial')
  save(RUN/'teaching.json.gz',cls.teaching)
  cls.rows=cls.s.sample(balanced_cases(cls.m['examples'],2,12,cls.s.rng))
  cls.fit=cls.s.fit(RUN,'samples-0.json.gz',cls.rows)
  cls.parent=cls.s.checkpoint(RUN,'whole.json.gz')
 @classmethod
 def tearDownClass(cls):
  MEASURE.update(wall_seconds=time.perf_counter()-cls.started,reader_parameters=sum(p.numel() for p in cls.s.reader.parameters()),
   learning_updates=cls.s.reader.committed_updates,fit=cls.fit,files_bytes=sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file()),work=str(RUN))
 def fresh(self):return Student.restore(RUN,self.parent)
 def test_complete_correction_stage(self):
  s=self.fresh();previous=d.development(s,self.m)
  result=d.training_unit(s,self.m,RUN,1,'normal',previous)
  value=s.checkpoint(RUN,'whole-corrected.json.gz')
  restored=Student.restore(RUN,value)
  self.assertEqual(restored.reader.committed_updates,2400)
  self.assertEqual(len(restored.sample_refs),2)
  self.assertEqual(result['local_n'],16)
 def test_full_window_and_fields(self):
  for row in self.rows:
   q=row['question'];self.assertEqual(len(q['frames']),20);self.assertEqual(len(q['frames'][0]),28)
   self.assertEqual(q['end_us']-q['start_us'],1_000_000)
   self.assertEqual(q['selected_indices'],FRAME_INDEX)
   self.assertEqual(FRAME_INDEX[0],0);self.assertEqual(FRAME_INDEX[-1],19)
 def test_dense_to_sparse_and_actual_times(self):
  for cat in range(4):
   rows=[r for r in self.teaching['lessons'] if r['category']==cat]
   self.assertEqual(len(rows),13)
   gaps=np.diff([r['start_us'] for r in rows]);self.assertGreater(gaps[-1],np.median(gaps[:9]));self.assertGreater(gaps[-2],np.median(gaps[:9]))
   self.assertTrue(all(r['label']==int(cat!=0) for r in rows))
 def test_only_declared_query_input(self):
  s=self.fresh();q=s.question(0)
  self.assertEqual(q['input']['channels'],[[s.mapping['C0'],.8]])
  self.assertNotIn(s.mapping['P'],[x[0] for x in q['input']['channels']])
  with self.assertRaises(ValueError):s.question({'category':0,'answer':1})
 def test_observation_and_save_do_not_advance(self):
  s=self.fresh();before=s.state()
  for _ in range(4):s.core.graph();s.core.metrics();s.core.observation_nodes();s.state()
  self.assertEqual(before,s.state())
 def test_pause_restore_next_questions(self):
  a=self.fresh();ra=[a.question(c) for c in (3,0,2,1)];sa=a.state()
  b=self.fresh();rb=[b.question(c) for c in (3,0,2,1)];sb=b.state()
  self.assertEqual(ra,rb);self.assertEqual(sa,sb)
 def test_next_optimizer_update_preserved(self):
  x=[[r['question']['frames'][i] for i in FRAME_INDEX] for r in self.rows];y=[r['label'] for r in self.rows]
  a=self.fresh();before=a.core.capture_state().to_dict();a.reader.continue_calibration(x,y,steps=1);digest=a.reader_digest()
  b=self.fresh();b.reader.continue_calibration(x,y,steps=1)
  self.assertEqual(digest,b.reader_digest());self.assertEqual(a.core.capture_state().to_dict(),before)
  self.assertEqual(a.reader.committed_updates,1201);self.assertEqual(a.reader.computed_updates,1201)
 def test_reader_training_is_last_state(self):
  self.assertIn('last state',self.fit['selection']);self.assertEqual(self.fit['committed_updates'],1200)
 def test_corrective_conditions_and_old_examples(self):
  s=self.fresh();e=copy.deepcopy(self.m['development_examples'][0][0]);e['category']=0
  t=s.curriculum(self.m['examples'],'normal','correction-1',[e])
  self.assertEqual(t['dense_passes'],2);self.assertEqual(len(t['lessons']),25)
  self.assertEqual(set(r['category'] for r in t['lessons']),set(range(4)))
  self.assertEqual(sum(r['condition']==e for r in t['lessons']),5)
 def test_shuffled_preserves_teacher_dose(self):
  s=Student(2111000,'apparatus-shuffle');t=s.curriculum(self.m['examples'],'shuffled','initial')
  self.assertEqual(len(t['lessons']),52)
  self.assertEqual(sum(r['label']==0 for r in t['lessons']),13)
  self.assertTrue(any(r['label']!=int(r['category']!=0) for r in t['lessons']))
 def test_material_and_metadata_isolation(self):
  self.assertEqual(len(self.m['tests']),26)
  s=self.fresh();p=copy.deepcopy(self.m['tests'][0]);r=s.solve(p,limit=4)
  other=self.fresh();p['oracle']={'malicious':'unusable answer'};p['irrelevant_label']=7
  r2=other.solve(p,limit=4)
  self.assertEqual(r['steps'],r2['steps']);self.assertEqual(r['final_assignment'],r2['final_assignment'])
 def test_environment_and_continuity(self):
  s=self.fresh();p=self.m['tests'][0];before=s.core.time_us;r=s.solve(p,limit=8)
  self.assertEqual(s.core.time_us-before,3*len(r['steps'])*1_000_000)
  a=r['initial_assignment'][:]
  for st in r['steps']:
   self.assertIn(st['clause'],d.sat.unsatisfied(p['clauses'],a))
   self.assertEqual(st['breaks'],[d.sat.break_count(p['clauses'],a,v) for v in st['candidates']])
   v=st['candidates'][st['selected']];a[v]=not a[v];self.assertEqual(a,st['assignment'])
  self.assertEqual(r['solved'],d.sat.verify_witness(p['n'],p['clauses'],a))
 def test_full_development_cost(self):
  s=self.fresh();t=time.perf_counter();result=d.development(s,self.m)
  save(RUN/'development.json.gz',result)
  MEASURE['development_seconds']=time.perf_counter()-t
  MEASURE['development_local_correct']=result['local_correct'];MEASURE['development_sat_solved']=result['sat_solved']
  self.assertEqual(result['local_n'],16);self.assertEqual(result['sat_n'],4)
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Apparatus)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 summary=dict(passed=result.wasSuccessful(),tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),
              source_sha256={x:sha(d.HERE/x) for x in ('student.py','driver.py','test_apparatus.py')},measurements=MEASURE)
 (d.HERE/'apparatus-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False));raise SystemExit(0 if result.wasSuccessful() else 1)
