"""Isolated non-cohort tests; never load a formal parent or select an encoding by scores."""
import copy,json,random,time,unittest
from pathlib import Path
from unittest.mock import patch
import torch
import study as d
RUN=d.ROOT/'.work'/('sat-exclusion-apparatus-'+str(time.time_ns()))
RUN.mkdir(parents=True)
class Checks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  torch.set_num_threads(1);cls.folder=RUN/'parents/o0';cls.folder.mkdir(parents=True)
  s=d.Student(3111000,'apparatus-only');s.checkpoint(cls.folder,'whole-birth.json.gz')
  rows=[{'condition':{'category':c},'question':s.question(c),'label':int(c!=0)} for c in list(range(4))*4]
  d.save(cls.folder/'samples-0.json.gz',rows);s.sample_refs=['samples-0.json.gz']
  s.reader.continue_calibration([[r['question']['frames'][i] for i in d.FRAME_INDEX] for r in rows],[r['label'] for r in rows],steps=1)
  cls.parent=s.checkpoint(cls.folder,'whole-test-026.json.gz')
  d.save(RUN/'templates/o0.json.gz',d.create_templates(3111000))
  cls.parent_hash=d.sha(cls.folder/'whole-test-026.json.gz')
 def test_restoration_is_exact(self):
  a=d.Branch(RUN,0,'intact');b=d.Branch(RUN,0,'restored')
  self.assertEqual(a.s.state(),b.s.state())
  self.assertEqual([a.question(c) for c in (0,2,1,3)],[b.question(c) for c in (0,2,1,3)])
 def test_blank_replaces_only_core_history(self):
  b=d.Branch(RUN,0,'blank-core')
  self.assertEqual(b.s.core.time_us,0);self.assertEqual(b.s.input_count,0)
  self.assertEqual(b.reader_digest(),self.parent['reader_digest'])
  self.assertEqual(b.mapping,self.parent['mapping'])
 def test_no_core_paths(self):
  with patch.object(d.base,'create_engine',side_effect=AssertionError('Core called by bypass')):
   for arm in d.ARMS[3:8]:
    b=d.Branch(RUN,0,arm);q=b.question(2)
    self.assertIsNone(b.s);self.assertEqual(len(q['frames']),20)
 def test_relay_does_not_compute_preference(self):
  b=d.Branch(RUN,0,'relay-fixed')
  for c in range(4):
   q=b.question(c);v=q['frames'][0]
   self.assertTrue(all(x==q['frames'][0] for x in q['frames']))
   self.assertEqual(sum(x>0 for x in v),4)
   j=b.reader.layout.index[b.mapping['C'+str(c)]]*4
   self.assertAlmostEqual(v[j],.8)
   for name in ('P','N'):self.assertEqual(sum(v[b.reader.layout.index[b.mapping[name]]*4:][:4]),0)
 def test_constant_has_no_category_information(self):
  b=d.Branch(RUN,0,'constant-fixed');q=[b.question(c) for c in range(4)]
  self.assertTrue(all(r['frames']==q[0]['frames'] and r['logits']==q[0]['logits'] for r in q))
 def test_template_has_no_teaching(self):
  t=d.load(RUN/'templates/o0.json.gz')
  self.assertEqual(len(t),4)
  for v in t.values():
   self.assertEqual(v['before']['input_count'],0);self.assertEqual(v['before']['lesson_times'],[])
   self.assertEqual(v['after']['learning_blocks'],0)
 def test_full_checkpoint_restore_next_query(self):
  for arm in ('intact','blank-core','relay-fixed','template-fixed','relay-trained'):
   b=d.Branch(RUN,0,arm);b.question(3);folder=RUN/f'origins/o0/{arm}';folder.mkdir(parents=True)
   value=b.checkpoint(folder,'test.json.gz',dict(stage='test',test=0))
   c=d.Branch.restore(RUN,folder,value)
   self.assertEqual(b.question(1),c.question(1))
   if b.s:
    for rel in b.s.sample_refs:self.assertTrue((folder/rel).is_file())
 def test_next_optimizer_step_preserved(self):
  b=d.Branch(RUN,0,'relay-trained');folder=RUN/'origins/o0/optimizer';folder.mkdir(parents=True)
  x=[[b.frames(c)[i] for i in d.FRAME_INDEX] for c in range(4)];y=[0,1,1,1]
  b.reader.continue_calibration(x,y,steps=1)
  value=b.checkpoint(folder,'before.json.gz',dict(stage='fit',cycle=0,test=0))
  c=d.Branch.restore(RUN,folder,value)
  b.reader.continue_calibration(x,y,steps=1);c.reader.continue_calibration(x,y,steps=1)
  self.assertEqual(b.reader_digest(),c.reader_digest());self.assertEqual(b.reader.committed_updates,2)
 def test_truth_isolation_and_valid_witness(self):
  p=d.sat.random_sat(5,18,random.Random(119));p.update(id='apparatus',rng_seed=123)
  a=d.Branch(RUN,0,'relay-fixed');r=a.solve(p)
  poison=copy.deepcopy(p);poison['oracle']={'malicious':'wrong'};poison['answer']=object()
  b=d.Branch(RUN,0,'relay-fixed');s=b.solve(poison)
  self.assertEqual(r['steps'],s['steps']);self.assertEqual(r['solved'],d.sat.verify_witness(p['n'],p['clauses'],r['final_assignment']))
 def test_parent_unchanged_and_reading_inert(self):
  b=d.Branch(RUN,0,'intact');before=b.s.state()
  b.s.core.observation_nodes();b.s.core.capture_state();b.s.core.graph()
  self.assertEqual(before,b.s.state());self.assertEqual(d.sha(self.folder/'whole-test-026.json.gz'),self.parent_hash)
if __name__=='__main__':
 start=time.perf_counter();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 out=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),work=str(RUN),wall_seconds=time.perf_counter()-start,
  source_sha256={n:d.sha(d.HERE/n) for n in ('study.py','test_apparatus.py')})
 (d.HERE/'apparatus-summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out));raise SystemExit(0 if result.wasSuccessful() else 1)