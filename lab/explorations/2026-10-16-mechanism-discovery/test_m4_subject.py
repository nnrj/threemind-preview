"""New immutable-corpus whole-state fixture, excluded from scientific origins."""
import gc
import json
import time
import unittest
from uuid import uuid4

import numpy as np
import torch

from m4_instrument import ROOT,window,digest
from m4_instrument_driver import InstrumentGuard
from m4_subject import Subject


class SubjectTests(unittest.TestCase):
    def test_external_corpus_complete_restoration_and_future_updates(self):
        torch.set_num_threads(1)
        folder=ROOT/'.work'/('m4-subject-fixture-'+uuid4().hex)
        folder.mkdir(parents=True)
        with InstrumentGuard(folder) as guard:
            self.assertTrue(guard.thread.is_alive())
            a=Subject(1119004,identity='m4-subject-fixture',data_root=folder)
            a.session.world.set_scene([(0,0)],positions=[[.4,.3]])
            rows=[a.session.tick(eye=(.1,0.),hand=(0.,.1)) for _ in range(2)]
            a.cursor=2
            values={'x':window(a.motor.layout,rows)[None],'eye':[0],'hand':[1],'move':[1]}
            reference=a.add_samples('fixture-one',values,metadata={'phase':'instrument-only'})
            arrays=a.training_arrays()
            a.motor.continue_calibration(arrays['x'],arrays['eye'],arrays['hand'],arrays['move'],steps=2,batch_size=1)
            before=digest(a.canonical());a.save(folder/'checkpoint')
            self.assertEqual(before,digest(a.canonical()))
            b=Subject.restore(folder/'checkpoint',data_root=folder)
            self.assertEqual(before,digest(b.canonical()))
            self.assertEqual(reference,b.corpus[0]);self.assertEqual(b.motor.committed_updates,2)
            b.session.engine.graph();b.session.engine.metrics();b.session.engine.capture_state()
            time.sleep(.01);self.assertEqual(before,digest(b.canonical()))
            for subject in (a,b):
                row=subject.session.tick(eye=(-.1,0.),hand=(0.,-.1));subject.cursor+=1
                x=window(subject.motor.layout,[row])[None]
                subject.motor.continue_calibration(x,[1],[0],[1],steps=2,batch_size=1)
            self.assertEqual(digest(a.canonical()),digest(b.canonical()))
            self.assertEqual(a.session.engine.time_us,150000)
            with self.assertRaises(FileExistsError):a.add_samples('fixture-one',values,metadata={})
            with self.assertRaises(ValueError):a.dependency(reference|{'path':'../outside.npz'})
            with self.assertRaises(ValueError):a.dependency(reference|{'sha256':'0'*64})
            with self.assertRaises(ValueError):a.add_samples('fractional-label',values|{'eye':[.5]},metadata={})
            self.assertEqual(digest(a.canonical()),digest(b.canonical()))
            print(json.dumps({'fixture':str(folder),'passed':True,'whole_sha256':before,
                              'future_sha256':digest(a.canonical()),'scientific_origins':0,'updates':4}))
            del a,b;gc.collect()
        self.assertFalse((folder/'STOP').exists())


if __name__=='__main__':unittest.main()
