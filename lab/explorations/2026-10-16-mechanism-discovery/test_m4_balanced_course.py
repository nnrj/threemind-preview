"""Preparation fixtures: schedule balance, physical reachability, truth isolation."""
from collections import Counter
import gc
import json
import unittest
from uuid import uuid4

import torch

from m4_instrument import ROOT,digest
from m4_instrument_driver import InstrumentGuard
from m4_subject import Subject
import m4_balanced_course as c


class BalancedCourseTests(unittest.TestCase):
    def test_frozen_generator_balances_training_and_keeps_final_materials_separate(self):
        for origin in range(8):
            b=c.bank(origin)
            lessons=[t for cycle in b['teaching_rounds'] for block in cycle for t in block]
            self.assertEqual(Counter(t['mode'] for t in lessons),Counter(dict.fromkeys(c.MODES,16)))
            self.assertEqual(Counter((t['mode'],t['alias']) for t in lessons),Counter({(m,a):8 for m in c.MODES for a in (0,1)}))
            for mode in c.MODES:
                self.assertEqual(Counter(tuple(t['xy']) for t in lessons if t['mode']==mode),Counter(dict.fromkeys(c.POSITIONS,2)))
            self.assertEqual(b['ordinary_seconds'],255)
            self.assertTrue({tuple(t['xy']) for t in b['confirmation']}.isdisjoint({tuple(t['xy']) for t in lessons}))
            self.assertEqual({t['alias'] for t in b['development']},{0})
            self.assertEqual({t['alias'] for t in b['confirmation']},{1})

    def test_teacher_physics_and_autonomous_metadata_isolation(self):
        torch.set_num_threads(1)
        folder=ROOT/'.work'/('m4-course-fixture-'+uuid4().hex);folder.mkdir(parents=True)
        results=[];hashes=[]
        with InstrumentGuard(folder) as guard:
            self.assertTrue(guard.thread.is_alive())
            a=Subject(1119006,identity='m4-course-fixture',data_root=folder)
            for i,mode in enumerate(c.MODES):
                t=c.task(f'instrument-{i}',mode,c.POSITIONS[i],0)
                rows,values,result,samples=c.trial(a,t,teaching=True)
                self.assertEqual(len(rows),60);self.assertEqual(len(samples),6)
                self.assertEqual(values['move'],[int(mode!='eye')]*6)
                self.assertTrue(result['joint_success'],result)
                self.assertIsNone(result['autonomous_success'])
                a.add_samples(t['id'],values,metadata={'phase':'N0 teaching instrument'})
                results.append(result)
            a.save(folder/'parent');reference=digest(a.canonical());del a;gc.collect()
            # Same complete parent, cue and actual physical input; only the
            # scorer's mode label differs. It must never affect student actions.
            for label in ('eye','hand'):
                a=Subject.restore(folder/'parent',data_root=folder)
                t=c.task('metadata-isolation',label,c.POSITIONS[3],0);t['cue']='看'
                rows,_,result,_=c.trial(a,t,teaching=False)
                self.assertTrue(all(not r['assistance'] for r in rows))
                hashes.append(digest(a.canonical()));del a;gc.collect()
            self.assertEqual(hashes[0],hashes[1])
        self.assertFalse((folder/'STOP').exists())
        print(json.dumps({'fixture':str(folder),'teacher_results':results,'parent_sha256':reference,
                          'metadata_isolation_hashes':hashes,'scientific_origins':0}))


if __name__=='__main__':unittest.main()
