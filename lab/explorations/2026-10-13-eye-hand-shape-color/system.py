"""E69 complete individual and truth-free physical executor; no Core changes."""
import copy
import gzip
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.centered_recognition import WORDS
from lab.tools.continuous_foveal_motor import ContinuousFovealMotor
from lab.tools.sensorimotor_session import SensorimotorSession

SCHEMA = 'threemind.eye-hand-language-system/1'


def window(layout, rows):
    """Eight raw samples from the first request sample through the current one."""
    if not rows:
        return np.zeros((8, layout.width), dtype=np.float32)
    indices = np.rint(np.linspace(0, len(rows)-1, 8)).astype(int)
    return np.stack([layout.frame(rows[i]['activity']) for i in indices])


class Executor:
    """Only predicted receptors, calibrated geometry and the body's own state."""
    def __init__(self):
        self.eye_target = None
        self.hand_target = None
        self.waiting = True
        self.last_intent = None

    def accept(self, intent, observation, world):
        if intent is None:
            return
        self.last_intent = copy.deepcopy(intent)
        receptor = int(intent['eye_receptor'])
        if not 0 <= receptor < len(world.cells):
            raise ValueError('invalid predicted eye receptor')
        center, width = world.retinal_centers[receptor], world.retinal_widths[receptor]
        uv = np.where(np.abs(center) <= width/2+1e-12, 0., center)
        camera = observation['camera']
        ray = np.array(camera['forward']) + uv[0]*np.array(camera['right']) + uv[1]*np.array(camera['up'])
        base = -world.origin/np.linalg.norm(world.origin)
        right = np.array([1., 0., 0.]); up = np.cross(right, base)
        self.eye_target = [float(np.arctan2(ray@right, ray@base)),
                           float(np.arctan2(ray@up, np.hypot(ray@right, ray@base)))]
        if not intent['move']:
            if not self.waiting or self.hand_target is None:
                self.hand_target = [world.pointer.x, world.pointer.y]
            self.waiting = True
        else:
            receptor = int(intent['hand_receptor'])
            if not 0 <= receptor < len(world.cells):
                raise ValueError('invalid predicted hand receptor')
            ray = world.selected_ray(receptor, observation)
            if ray[2] >= -1e-8:
                raise ValueError('predicted ray does not meet the tabletop')
            self.hand_target = (world.origin+(.16-world.origin[2])/ray[2]*ray)[:2].tolist()
            self.waiting = False

    def commands(self, world):
        eye = np.zeros(2) if self.eye_target is None else world.eye_servo(self.eye_target)
        hand = (np.zeros(2) if self.hand_target is None else
                np.clip(3*(np.array(self.hand_target)-[world.pointer.x, world.pointer.y])
                        -.9*np.array([world.pointer.vx, world.pointer.vy]), -1, 1))
        return eye, hand

    def state(self):
        return copy.deepcopy({'eye_target': self.eye_target, 'hand_target': self.hand_target, 'waiting': self.waiting,
                                  'last_intent': self.last_intent})

    @classmethod
    def restore(cls, value):
        result = cls()
        result.eye_target = value['eye_target']; result.hand_target = value['hand_target']
        result.waiting = value['waiting']
        result.last_intent = value['last_intent']
        return result


class EyeHandSystem:
    def __init__(self, *, identity='e69-5.1-223', device='cpu', backend='native', data_root=None):
        self.identity = identity
        self.data_root = Path(data_root).resolve() if data_root else None
        self.session = SensorimotorSession(ActiveEyeClassroom(seed=91, weather_seed=47), seed=223,
                    kernel_id='threemind.continuous-memory/5.1', backend=backend)
        s = self.session; w = s.world
        blank=s.engine.capture_state().to_dict()
        if int(blank['time_us']) or blank['nodes'] or blank['edges']:
            raise ValueError('new formal subject requires an empty Core at simulated time zero')
        self.motor = ContinuousFovealMotor(s.layout.channels, w.channels[:w.vision_width],
                    w.retinal_centers, w.retinal_widths, identity=identity, seed=223).to(device)
        self.words = CalibratedActivity(s.layout.channels, WORDS, identity, seed=223).to(device)
        self.executor = Executor()
        self.phase = 'birth'
        self.cursor = 0
        # Data are immutable managed originals, not copies repeated at every boundary.
        self.corpora = []
        self.meter = {}

    def verify_dependencies(self):
        for ref in self.corpora:
            if self.data_root is None:
                raise ValueError('managed data root required for calibration dependencies')
            if Path(ref['path']).is_absolute() or Path(ref['path']).drive:
                raise ValueError('relative managed calibration reference required')
            path = (self.data_root/ref['path']).resolve()
            if not path.is_relative_to(self.data_root) or not path.is_file():
                raise ValueError('missing or unsafe calibration dependency')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != ref['sha256']:
                raise ValueError('calibration dependency changed')

    def describe(self):
        return {'identity': self.identity, 'time_us': self.session.engine.time_us,
                    'learning': {name: {'computed_updates': head.computed_updates,
                                         'committed_updates': head.committed_updates}
                              for name, head in (('motor', self.motor), ('words', self.words))}}

    def save(self, folder):
        self.verify_dependencies()
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError(folder)
        temporary = folder.with_name(folder.name+'.partial')
        temporary.mkdir(parents=True, exist_ok=False)
        s = self.session
        value = {'schema': SCHEMA, 'identity': self.identity, 'phase': self.phase, 'cursor': self.cursor,
                     'session': s.snapshot(), 'history': list(s.history), 'current': s.current,
                     'published': s.stream.published, 'layout': list(s.layout.channels), 'sensor': asdict(s.sensor.config),
                     'executor': self.executor.state(), 'corpora': self.corpora, 'meter': self.meter}
        with gzip.open(temporary/'system.json.gz', 'xt', encoding='utf-8', compresslevel=1) as out:
            json.dump(value, out, ensure_ascii=False, allow_nan=False)
        self.motor.save(temporary/'motor'); self.words.save(temporary/'words')
        (temporary/'dependencies.json').write_text(json.dumps({'corpora': self.corpora}), encoding='utf-8')
        (temporary/'complete.json').write_text(json.dumps(dict(schema=SCHEMA, **self.describe())), encoding='utf-8')
        for retry in range(4):
            try:
                temporary.rename(folder)
                break
            except PermissionError:
                if retry == 3:
                    raise
                time.sleep(.25*(retry+1))

    @classmethod
    def restore(cls, folder, *, device='cpu', backend='native', data_root=None):
        folder = Path(folder)
        manifest = json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        with gzip.open(folder/'system.json.gz', 'rt', encoding='utf-8') as source:
            value = json.load(source)
        if value['schema'] != SCHEMA or manifest['schema'] != SCHEMA or value['identity'] != manifest['identity']:
            raise ValueError('wrong whole-system identity')
        obj = cls.__new__(cls); obj.identity = value['identity']
        obj.data_root = Path(data_root).resolve() if data_root else None
        obj.corpora = value['corpora']
        obj.verify_dependencies()
        obj.session = SensorimotorSession(state=value['session'], dt_us=value['session']['dt_us'], backend=backend)
        s = obj.session
        if list(s.layout.channels) != value['layout'] or asdict(s.sensor.config) != value['sensor']:
            raise ValueError('sensory mapping changed')
        s.current = value['current']; s.history.extend(value['history']); s.stream.published = value['published']
        obj.motor = ContinuousFovealMotor.restore(folder/'motor', device=device, expected_identity=obj.identity)
        obj.words = CalibratedActivity.restore(folder/'words', device=device)
        if obj.words.identity != obj.identity or obj.motor.layout.channels != s.layout.channels or obj.words.layout.channels != s.layout.channels:
            raise ValueError('personal peripheral mismatch')
        obj.executor = Executor.restore(value['executor'])
        obj.phase = value['phase']; obj.cursor = value['cursor']; obj.meter = value['meter']
        if obj.describe() != {k: manifest[k] for k in ('identity', 'time_us', 'learning')}:
            raise ValueError('incomplete current state')
        return obj
