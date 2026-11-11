"""Atomic complete-organism snapshots, independent of legacy Core-only saves."""
import copy
import gzip
import json
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from lab.tools.sensorimotor_session import SensorimotorSession, WORLD_TYPES
from lab.tools.developmental_world import DevelopmentalWorld, VERSION as WORLD_VERSION
from lab.tools.developmental_motor import DevelopmentalMotor
from lab.tools.continuous_motor import recent_window

VERSION = 'threemind.developmental-system/2'
LEGACY_VERSION = 'threemind.developmental-system/1'
WORLD_TYPES[WORLD_VERSION] = DevelopmentalWorld


class DevelopmentalSession:
    def __init__(self, *, seed=223, identity=None, device='cpu'):
        self.identity = identity or str(uuid4())
        self.session = SensorimotorSession(DevelopmentalWorld(seed=seed), seed=seed)
        w = self.session.world
        self.motor = DevelopmentalMotor(self.session.layout.channels, w.channels[:w.vision_width], identity=self.identity, seed=seed).to(device)
        self.phase = 'birth'; self.parent = None; self.branch = 'intact'; self.tick_count = 0

    def window(self):
        return recent_window(self.motor.layout, self.session.history)

    def step(self, text_frame=None, *, teacher_pose=None, assistance=0., learn=False, variation=0., passive=False, guard=lambda: None):
        if not 0 <= assistance <= 1 or (learn or assistance) and teacher_pose is None:
            raise ValueError('teacher intervention must be explicit')
        s = self.session
        past = self.window() if s.history else None
        intent = self.motor.intent(past) if past is not None else None
        own = s.world.execute_pose(intent)
        noise = self.motor.variation(s.dt_us/1e6, variation)
        teacher = s.world.execute_pose(teacher_pose) if teacher_pose is not None else own
        command = (1-assistance)*own+assistance*teacher+noise[:4]
        command = command.clip(-1, 1)
        if passive: command *= 0
        row = s.tick(text_frame, eye=command[:2], hand=command[2:], mouth=noise[4:] if not passive else (0., 0.), guard=guard)
        # Evidence is attached to the same row already retained in history.
        row['development'] = {'identity': self.identity, 'phase': self.phase, 'branch': self.branch,
            'motor_steps_before': self.motor.steps, 'intent_pose': None if intent is None else intent.tolist(),
            'own_command': own.tolist(), 'teacher_command': teacher.tolist() if assistance else None,
            'teacher_pose': list(teacher_pose) if teacher_pose is not None else None,
            'assistance': assistance, 'variation': noise.tolist(), 'passive_control': bool(passive)}
        if learn and past is not None:
            # The current Core sample already received this teacher's physical
            # marker/text. It was published BEFORE executing this tick's force,
            # so it cannot contain the resulting body-motion feedback.
            row['development']['supervision_time_us'] = s.current['time_us']
            row['development']['loss'] = self.motor.teach(self.window(), teacher_pose)
        self.tick_count += 1
        return row

    def save(self, folder):
        folder = Path(folder)
        if folder.exists(): raise FileExistsError(folder)
        temporary = folder.with_name(folder.name+'.partial')
        temporary.mkdir(parents=True, exist_ok=False)
        s = self.session
        state = {'schema': VERSION, 'identity': self.identity, 'phase': self.phase, 'branch': self.branch,
            'parent': self.parent, 'tick_count': self.tick_count, 'session': s.snapshot(),
            'current': copy.deepcopy(s.current), 'history': list(s.history), 'published': s.stream.published,
            'sensor': asdict(s.sensor.config), 'layout': list(s.layout.channels)}
        with gzip.open(temporary/'system.json.gz', 'xt', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False, allow_nan=False)
        self.motor.save(temporary/'motor')
        (temporary/'complete.json').write_text(json.dumps({'schema': VERSION, 'identity': self.identity,
            'core_time_us': s.engine.time_us, 'motor_steps': self.motor.steps, 'tick_count': self.tick_count}), encoding='utf-8')
        # Windows scanners may briefly hold a completed file. Never replace an
        # existing snapshot; retain the complete .partial on a persistent error.
        for attempt in range(4):
            try:
                temporary.rename(folder)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(.25 * (attempt + 1))
        self.parent = str(folder)

    @classmethod
    def restore(cls, folder, *, device='cpu', branch=None):
        folder = Path(folder)
        manifest = json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        with gzip.open(folder/'system.json.gz', 'rt', encoding='utf-8') as stream: state = json.load(stream)
        if state['schema'] not in (VERSION, LEGACY_VERSION) or manifest['schema'] != state['schema'] or manifest['identity'] != state['identity']:
            raise ValueError('complete system identity/version mismatch')
        obj = cls.__new__(cls); obj.identity = state['identity']
        obj.motor = DevelopmentalMotor.restore(folder/'motor', device=device, expected_identity=obj.identity)
        if state['schema'] == LEGACY_VERSION and obj.motor.steps:
            raise ValueError('legacy pre-arrival supervision requires a separately authorized research branch')
        obj.session = SensorimotorSession(state=state['session'], dt_us=state['session']['dt_us'])
        s = obj.session
        if list(s.layout.channels) != state['layout'] or s.layout.channels != obj.motor.layout.channels or asdict(s.sensor.config) != state['sensor']:
            raise ValueError('sensory mapping/configuration mismatch')
        s.current = state['current']; s.history.extend(state['history']); s.stream.published = state['published']
        obj.phase = state['phase']; obj.branch = state['branch'] if branch is None else str(branch)
        obj.parent = str(folder); obj.tick_count = state['tick_count']
        if manifest['core_time_us'] != s.engine.time_us or manifest['motor_steps'] != obj.motor.steps or manifest['tick_count'] != obj.tick_count:
            raise ValueError('incomplete system state')
        if branch is not None:
            # Explicit experimental fork: the sibling keeps identical weights,
            # optimizer and RNG but must not accept another sibling's peripheral.
            obj.identity = obj.identity+'/'+str(branch)
            obj.motor.identity = obj.identity
        return obj
