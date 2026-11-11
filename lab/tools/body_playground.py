"""An unsupervised toy table: whole-field eye, proprioception, touch and sound.

Objects have mass, springs, damping and soft contact. Optical rays use MuJoCo;
table mechanics and band-energy acoustics are explicit reduced-order models,
not a fluid/body/ear biophysics claim. No task target enters sensory encoding.
"""
import copy
import numpy as np
import mujoco
from threemind_core import Stimulus
from lab.tools.eye_hand_world import EyeHandWorld
from lab.tools.active_eye import EyeConfig
from lab.tools.shape_color_world import Pointer

VERSION = 'threemind.body-playground/1'


class BodyPlayground(EyeHandWorld):
    def __init__(self, seed=91, weather_seed=47, *, config=None, visible_self=True, nose=False, toys=True):
        self.toys = bool(toys)
        self.toy_velocity = np.zeros((4, 2)); self.resonance = np.zeros(4)
        self.voice = np.zeros(2); self.touch = np.zeros(2)
        self.contact_count = 0; self.contacting = np.zeros(4, dtype=bool)
        self.masses = np.array([.22, .31, .28, .18])
        self.stiffness = np.array([1.1, 1.4, .8, 1.6])
        super().__init__(seed, weather_seed, config=config, visible_self=visible_self, nose=nose)
        self.set_scene([(0, 0), (1, 1), (2, 2), (3, 3)],
                       positions=[[-.28, -.22], [.31, -.27], [-.32, .34], [.29, .28]])

    @property
    def channels(self):
        return super().channels + tuple(self.wiring.identity(0xE61000+i) for i in range(16))

    def set_scene(self, items, variant=0, positions=None):
        if len(items) != 4: raise ValueError('playground /1 has four calibrated physical toys')
        super().set_scene(items, variant, positions)
        self.anchors = np.array(self.positions, dtype=float)
        self.toy_velocity = np.zeros((len(items), 2)); self.resonance = np.zeros(len(items))
        self.contacting = np.zeros(len(items), dtype=bool)
        self.external_forces = np.zeros((len(items),2))
        self.external_sound = np.zeros(4)
        self.external_sound_position = np.array([0.,.5])
        self.object_ids = [mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, 'o'+str(i)) for i in range(len(items))]

    def _sync_toys(self):
        for geom, xy in zip(self.object_ids, self.positions): self.model.geom_pos[geom, :2] = xy

    def advance_physics(self, action=(0., 0.), dt=.05, *, eye_action=(0., 0.), mouth=(0., 0.)):
        mouth = np.asarray(mouth, dtype=float)
        if mouth.shape != (2,) or not np.isfinite(mouth).all() or not 0 < dt <= .1:
            raise ValueError('finite two-dimensional mouth and bounded step')
        # Aperture and tension control a three-band source; there are no words.
        self.voice = np.array([max(0., float(np.clip(mouth[0], -1, 1))), float(np.clip(mouth[1], -1, 1))])
        contact_sum = np.zeros(2); touching = np.zeros(len(self.items), dtype=bool)
        steps = max(1, int(np.ceil(dt/.005))); h = dt/steps
        for _ in range(steps):
            super().advance_physics(action, h, eye_action=eye_action)
            self.resonance *= np.exp(-h/.22)
            if not self.toys: continue
            xy = np.array(self.positions); p = np.array([self.pointer.x, self.pointer.y])
            pv = np.array([self.pointer.vx, self.pointer.vy]); reaction = np.zeros(2)
            for i in range(len(xy)):
                delta = xy[i]-p; distance = float(np.linalg.norm(delta))
                normal = delta/distance if distance > 1e-9 else np.array([1., 0.])
                penetration = max(0., .20-distance)
                contact = max(0., 35*penetration + .6*float((pv-self.toy_velocity[i])@normal)) if penetration else 0.
                force = contact*normal
                touching[i] |= bool(contact)
                # Positive compression work excites a damped material resonance.
                work = max(0., float(force@(pv-self.toy_velocity[i])))*h
                self.resonance[i] += work
                reaction -= force
                outside=self.external_forces[i]
                self.resonance[i] += max(0.,float(outside@self.toy_velocity[i]))*h
                acceleration = (force+outside-self.stiffness[i]*(xy[i]-self.anchors[i])-.35*self.toy_velocity[i])/self.masses[i]
                self.toy_velocity[i] = np.clip(self.toy_velocity[i]+h*acceleration, -1.5, 1.5)
                proposed = xy[i]+h*self.toy_velocity[i]
                hit = np.abs(proposed) > .83
                xy[i] = np.clip(proposed, -.83, .83); self.toy_velocity[i][hit] = 0.
            pv = np.clip(pv+h*reaction, -1., 1.)
            self.pointer.vx, self.pointer.vy = map(float, pv)
            self.positions = xy.tolist(); contact_sum += reaction/steps
        self.touch = contact_sum
        self.contact_count += int(np.sum(touching & ~self.contacting))
        self.contacting = touching
        self._sync_toys()

    def acoustic_bands(self):
        # Squared-pressure bands, not semantic/object identity channels.
        result = np.zeros((2, 4))
        for e, ear in enumerate(([-.07, -.15], [.07, -.15])):
            result[e] += self.external_sound/(1+float(np.sum((self.external_sound_position-ear)**2)))
            for i, xy in enumerate(self.positions):
                d2 = float(np.sum((np.asarray(xy)-ear)**2))
                result[e, i % 4] += self.resonance[i]/(1+d2)
            pitch = (self.voice[1]+1)
            weights = np.maximum(0., 1-np.abs(np.arange(3)-pitch))
            result[e, :3] += .05*self.voice[0]**2*weights
            result[e, 3] += .002*float(np.sum(np.square(self.weather()[:2])))
        return np.sqrt(result)

    def observe(self, *, motor_only=False):
        self._sync_toys(); ob = super().observe(motor_only=motor_only)
        ears = self.acoustic_bands().ravel()
        # Contact x/y, aperture, signed tension, emitted power: 8 values.
        extra = [max(0., self.touch[0]/10), max(0., -self.touch[0]/10),
                 max(0., self.touch[1]/10), max(0., -self.touch[1]/10),
                 self.voice[0], max(0., self.voice[1]), max(0., -self.voice[1]), self.voice[0]**2]
        return ob | {'schema': VERSION, 'values': ob['values']+ears.tolist()+extra,
            'ears_band_pressure': ears.tolist(), 'mouth_state': self.voice.tolist(),
            'toy_touch_force_N': self.touch.tolist(), 'toy_resonance_J': self.resonance.tolist(),
            'toy_velocity_m_s': self.toy_velocity.tolist(), 'toys_active': self.toys,
            'toy_contacts': self.contact_count, 'toy_anchors_m': self.anchors.tolist(),
            'external_force_N':self.external_forces.tolist(),'external_sound_power':self.external_sound.tolist()}

    def stimulus(self, observation):
        v = np.asarray(observation['values'], dtype=float)
        if observation['schema'] != VERSION or v.shape != (len(self.channels),) or not np.isfinite(v).all() or np.min(v) < 0:
            raise ValueError('finite playground measurements')
        gains = [self.eye_config.visual_gain]*self.vision_width + [.5]*8 + [.02]*24 + [.05]*10 + [.05]*16
        return Stimulus(0, tuple((ch, float(x*g)) for ch,x,g in zip(self.channels,v,gains) if x > 0), intensity=1.)

    def state(self):
        return super().state() | {'schema': VERSION, 'toys': self.toys, 'anchors': self.anchors.tolist(),
            'toy_velocity': self.toy_velocity.tolist(), 'resonance': self.resonance.tolist(),
            'voice': self.voice.tolist(), 'touch': self.touch.tolist(), 'contact_count': self.contact_count,
            'contacting': self.contacting.tolist(),'external_forces':self.external_forces.tolist(),
            'external_sound':self.external_sound.tolist(),'external_sound_position':self.external_sound_position.tolist()}

    @classmethod
    def restore(cls, state):
        if state['schema'] != VERSION: raise ValueError('playground version')
        w = cls(state['seed'], state['weather_seed'], config=EyeConfig(**state['eye_config']),
                visible_self=state['visible_self'], nose=state['nose'], toys=state['toys'])
        w.set_scene(state['items'], state['variant'], state['positions']); w.pointer = Pointer(**state['pointer'])
        for k in ('marker', 'time_s', 'body_temperature', 'acceleration', 'motor_power', 'contact_force', 'eye_power', 'contact_count'):
            setattr(w, k, copy.deepcopy(state[k]))
        for k in ('anchors', 'toy_velocity', 'resonance', 'voice', 'touch', 'eye_angle', 'eye_velocity', 'contacting'):
            setattr(w, k, np.asarray(state[k]))
        for k in ('external_forces','external_sound','external_sound_position'):
            if k in state:setattr(w,k,np.asarray(state[k]))
        w._sync_toys(); w._refresh_directions(); return w


class ExploratoryMotor:
    """Fixed anonymous wiring plus separately recorded unconditioned variation.

No training labels, scene, clock, reward, target or sensory metadata are read.
Variation is an external motor-development condition, not Core intention.
"""
    def __init__(self, width, seed=71, noise_std=.18, activity_gain=1.):
        self.rng = np.random.default_rng(seed)
        self.weights = self.rng.normal(0, .18, (6, width))
        self.noise = np.zeros(6); self.noise_std = float(noise_std)
        self.activity_gain = float(activity_gain)
        if not 0 <= self.noise_std <= .5: raise ValueError('bounded motor variation')
        if not 0 <= self.activity_gain <= 1: raise ValueError('bounded actuator gain')

    def action(self, raw_activity, dt=.05):
        if not 0 < dt <= .1: raise ValueError('bounded positive motor interval')
        a = np.asarray(raw_activity, dtype=float)
        if a.shape != (self.weights.shape[1],) or not np.isfinite(a).all(): raise ValueError('raw activity vector')
        core = np.tanh(self.activity_gain*(self.weights@a))
        retention = np.exp(-dt/.35)
        self.noise = retention*self.noise + self.noise_std*np.sqrt(1-retention**2)*self.rng.normal(size=6)
        command = np.clip(core+self.noise, -1, 1)
        return command, {'core_component': core.tolist(), 'motor_variation': self.noise.tolist()}

    def state(self):
        return {'weights': self.weights.tolist(), 'noise': self.noise.tolist(), 'noise_std': self.noise_std, 'activity_gain':self.activity_gain,
                'rng': copy.deepcopy(self.rng.bit_generator.state)}

    @classmethod
    def restore(cls, state):
        w = cls(len(state['weights'][0]), noise_std=state['noise_std'],activity_gain=state.get('activity_gain',1.))
        w.weights = np.asarray(state['weights']); w.noise = np.asarray(state['noise'])
        w.rng.bit_generator.state = copy.deepcopy(state['rng']); return w
