"""Isolated fixture checks, never formal individuals or scientific N."""
import gc
import json
from pathlib import Path
import time
import unittest
from uuid import uuid4
import numpy as np
import psutil
import torch
from m4_instrument import Whole,calibrate_instrument,digest,ROOT


class InstrumentTests(unittest.TestCase):
    def test_random_ports_preserve_optics(self):
        a=Whole(1106004,identity='m4-instrument-fixture-a')
        b=Whole(1106005,identity='m4-instrument-fixture-b')
        self.assertNotEqual(a.session.world.channels,b.session.world.channels)
        self.assertNotEqual(a.session.sensor.identity(0x100001),b.session.sensor.identity(0x100001))
        self.assertEqual(a.session.world.retinal_centers.tolist(),b.session.world.retinal_centers.tolist())
        self.assertEqual(a.session.engine.time_us,0)
        self.assertEqual(b.session.engine.time_us,0)

    def test_complete_roundtrip_after_physical_input_and_learning(self):
        torch.set_num_threads(1)
        p=ROOT/'.work'/('m4-instrument-fixture-'+uuid4().hex)
        a=Whole(1106004,identity='m4-instrument-fixture')
        a.session.world.set_scene([(0,0)],positions=[[.4,.3]])
        a.session.world.marker=[.4,.3]
        a.session.world._refresh_directions()
        rows=[];started=time.perf_counter()
        frames=list(a.session.sensor.frames('看指'))
        for i in range(2):
            rows.append(a.session.tick(frames[i],eye=(.2,-.1),hand=(.2,.1)))
            a.cursor+=1
        elapsed=time.perf_counter()-started
        calibrate_instrument(a,rows)
        self.assertEqual(a.motor.committed_updates,2)
        self.assertEqual(a.session.engine.time_us,100000)
        a.save(p)
        b=Whole.restore(p)
        # Canonical JSON is the complete-state format: recording tuples become
        # arrays on disk. Compare every field through that declared encoding.
        self.assertEqual(digest(a.canonical()),digest(b.canonical()))
        before=digest(b.canonical())
        b.session.engine.graph();b.session.engine.metrics();b.session.engine.activations();b.session.engine.capture_state()
        self.assertEqual(before,digest(b.canonical()))
        # Subsequent continuous input and optimizer updates must also agree.
        ra=a.session.tick(eye=(0.,.1),hand=(.1,0.));rb=b.session.tick(eye=(0.,.1),hand=(.1,0.))
        self.assertEqual(ra,rb)
        a.cursor+=1;b.cursor+=1
        calibrate_instrument(a,[ra]);calibrate_instrument(b,[rb])
        self.assertEqual(digest(a.canonical()),digest(b.canonical()))
        print(json.dumps({'fixture':str(p),'two_ticks_wall_s':elapsed,'private_bytes':psutil.Process().memory_info().private,
                          'state_files_bytes':sum(f.stat().st_size for f in p.rglob('*') if f.is_file()),
                          'nodes':len(a.session.engine.capture_state().to_dict()['nodes']),
                          'edges':len(a.session.engine.capture_state().to_dict()['edges'])}))
        # An altered complete file is rejected, without loading a repaired subject.
        with (p/'system.json.gz').open('ab') as f:f.write(b'corrupt-fixture-only')
        with self.assertRaises(ValueError):Whole.restore(p)
        del a,b;gc.collect()


if __name__=='__main__':unittest.main()
