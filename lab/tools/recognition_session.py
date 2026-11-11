"""Whole-system checkpoint for a fixed-eye recognition/calibration experiment."""
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import time

from lab.tools.centered_recognition import CenteredWorld, WORDS
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.sensorimotor_session import SensorimotorSession

VERSION = 'threemind.recognition-system/1'


class RecognitionSystem:
    def __init__(self, *, seed=223, sensory_seed=91, device='cpu', identity='e64-blank-223',
                 kernel_id=None, kernel_config=None, backend='native'):
        self.identity, self.phase, self.cursor = identity, 'birth', 0
        world = CenteredWorld(seed=sensory_seed, toys=False)
        world.present(0, 4)
        self.session = SensorimotorSession(world, seed=seed, kernel_id=kernel_id,
                                          kernel_config=kernel_config, backend=backend)
        self.words = CalibratedActivity(self.session.layout.channels, WORDS, identity, seed=seed).to(device)

    def save(self, folder, *, compresslevel=9):
        p = Path(folder)
        if p.exists(): raise FileExistsError(p)
        temp = p.with_name(p.name+'.partial'); temp.mkdir(parents=True, exist_ok=False)
        s = self.session
        with gzip.open(temp/'system.json.gz', 'xt', encoding='utf-8', compresslevel=compresslevel) as f:
            json.dump(dict(schema=VERSION, identity=self.identity, phase=self.phase, cursor=self.cursor,
                session=s.snapshot(), current=s.current, history=list(s.history), published=s.stream.published,
                sensor=asdict(s.sensor.config), layout=s.layout.channels), f, ensure_ascii=False)
        self.words.save(temp/'words')
        (temp/'complete.json').write_text(json.dumps(dict(schema=VERSION, identity=self.identity,
            time_us=s.engine.time_us, updates=self.words.computed_updates)), encoding='utf-8')
        for retry in range(4):
            try: temp.rename(p); break
            except PermissionError:
                if retry == 3: raise
                time.sleep(.25*(retry+1))

    @classmethod
    def restore(cls, folder, device='cpu', *, backend='native'):
        p = Path(folder); m = json.loads((p/'complete.json').read_text(encoding='utf-8'))
        with gzip.open(p/'system.json.gz', 'rt', encoding='utf-8') as f: d = json.load(f)
        if m['schema'] != VERSION or d['schema'] != VERSION or m['identity'] != d['identity']:
            raise ValueError('complete recognition system required')
        a = cls.__new__(cls); a.identity, a.phase, a.cursor = d['identity'], d['phase'], d['cursor']
        a.words = CalibratedActivity.restore(p/'words', device)
        if a.words.identity != a.identity: raise ValueError('personal peripheral mismatch')
        s = a.session = SensorimotorSession(state=d['session'], dt_us=d['session']['dt_us'], backend=backend)
        s.current = d['current']; s.history.extend(d['history']); s.stream.published = d['published']
        if (m['time_us'] != s.engine.time_us or m['updates'] != a.words.computed_updates or
            list(s.layout.channels) != d['layout'] or asdict(s.sensor.config) != d['sensor']):
            raise ValueError('state, layout or learning mismatch')
        return a
