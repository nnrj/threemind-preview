"""Versioned toy body with a heavier hand and a breeze; old worlds unchanged."""
from dataclasses import asdict, dataclass
import numpy as np
from lab.tools.body_playground import BodyPlayground, VERSION as OLD_VERSION
from lab.tools.shape_color_world import Pointer

VERSION = 'threemind.developmental-world/1'


@dataclass(frozen=True)
class BodyConfig:
    mass_kg: float = 2.
    damping_N_s_m: float = 5.
    motor_force_N: float = 12.
    wind_fraction: float = .1

    def __post_init__(self):
        if not all(np.isfinite(v) for v in asdict(self).values()) or not .1 <= self.mass_kg <= 20 or not 0 < self.damping_N_s_m <= 30 or not 0 < self.motor_force_N <= 100 or not 0 <= self.wind_fraction <= 1:
            raise ValueError('finite physical body parameters')


class DevelopmentalWorld(BodyPlayground):
    def __init__(self, *args, body_config=None, **kwargs):
        self.body_config = body_config or BodyConfig()
        super().__init__(*args, **kwargs)

    def weather(self):
        wx, wy, temperature, humidity = super().weather()
        return wx*self.body_config.wind_fraction, wy*self.body_config.wind_fraction, temperature, humidity

    def advance_physics(self, action=(0., 0.), dt=.05, *, eye_action=(0., 0.), mouth=(0., 0.)):
        action, eye_action, mouth = [np.asarray(v, dtype=float) for v in (action, eye_action, mouth)]
        if any(v.shape != (2,) or not np.isfinite(v).all() for v in (action, eye_action, mouth)) or not 0 < dt <= .1:
            raise ValueError('finite commands and bounded physical step')
        self.voice = np.array([max(0., float(np.clip(mouth[0], -1, 1))), float(np.clip(mouth[1], -1, 1))])
        c, ec = self.body_config, self.eye_config
        steps = max(1, int(np.ceil(dt/.005))); h = dt/steps
        contact_sum = np.zeros(2); touching = np.zeros(len(self.items), dtype=bool)
        old_velocity = np.array([self.pointer.vx, self.pointer.vy]); eye_power = hand_power = 0.
        for _ in range(steps):
            wx, wy, air, _ = self.weather()
            p = np.array([self.pointer.x, self.pointer.y]); pv = np.array([self.pointer.vx, self.pointer.vy])
            force = c.motor_force_N*np.clip(action, -1, 1)
            pv += h*(force-c.damping_N_s_m*pv+.15*(np.array([wx, wy])-pv))/c.mass_kg
            pv = np.clip(pv, -1, 1); proposed = p+h*pv
            hit = np.abs(proposed) > 1; p = np.clip(proposed, -1, 1)
            self.contact_force = np.where(hit, -c.mass_kg*pv/h, 0.).tolist(); pv[hit] = 0.
            hand_power += float(np.sum(np.abs(force*pv)))/steps
            torque = ec.acceleration_rad_s2*np.clip(eye_action, -1, 1)
            self.eye_velocity = np.clip(self.eye_velocity+h*(torque-ec.damping_s_inv*self.eye_velocity), -ec.speed_limit_rad_s, ec.speed_limit_rad_s)
            next_angle = self.eye_angle+h*self.eye_velocity
            eye_hit = np.abs(next_angle) > ec.angle_limit_rad
            self.eye_angle = np.clip(next_angle, -ec.angle_limit_rad, ec.angle_limit_rad); self.eye_velocity[eye_hit] = 0.
            eye_power += float(np.sum(np.abs(torque*self.eye_velocity)))/steps
            self.resonance *= np.exp(-h/.22)
            reaction = np.zeros(2)
            if self.toys:
                xy = np.array(self.positions)
                for i in range(len(xy)):
                    delta = xy[i]-p; distance = float(np.linalg.norm(delta))
                    normal = delta/distance if distance > 1e-9 else np.array([1., 0.])
                    penetration = max(0., .20-distance)
                    contact = max(0., 35*penetration+.6*float((pv-self.toy_velocity[i])@normal)) if penetration else 0.
                    f = contact*normal; touching[i] |= bool(contact); reaction -= f
                    self.resonance[i] += max(0., float(f@(pv-self.toy_velocity[i])))*h
                    outside = self.external_forces[i]
                    self.resonance[i] += max(0., float(outside@self.toy_velocity[i]))*h
                    a = (f+outside-self.stiffness[i]*(xy[i]-self.anchors[i])-.35*self.toy_velocity[i])/self.masses[i]
                    self.toy_velocity[i] = np.clip(self.toy_velocity[i]+h*a, -1.5, 1.5)
                    proposed = xy[i]+h*self.toy_velocity[i]; hit = np.abs(proposed) > .83
                    xy[i] = np.clip(proposed, -.83, .83); self.toy_velocity[i][hit] = 0.
                self.positions = xy.tolist()
            pv = np.clip(pv+h*reaction/c.mass_kg, -1, 1)
            self.pointer = Pointer(*map(float, p), *map(float, pv)); contact_sum += reaction/steps
            self.body_temperature += h*(.4*(air-self.body_temperature)+.2*float(np.sum(np.abs(force*pv))))/20
            self.time_s += h
        self.acceleration = ((np.array([self.pointer.vx, self.pointer.vy])-old_velocity)/dt).tolist()
        self.motor_power, self.eye_power, self.touch = hand_power, eye_power, contact_sum
        self.contact_count += int(np.sum(touching & ~self.contacting)); self.contacting = touching
        self._sync_toys(); self._refresh_directions()

    def observe(self, **kwargs):
        ob = super().observe(**kwargs)
        # Same sensors and fixed conversion scales; support now bears the actual mass.
        ob['physical_background']['support_force_N'] = self.body_config.mass_kg*9.81
        ob['values'][self.vision_width+8+16] = self.body_config.mass_kg*9.81/10
        return ob | {'schema': VERSION, 'body_config': asdict(self.body_config)}

    def stimulus(self, observation):
        if observation['schema'] != VERSION: raise ValueError('developmental world version')
        return super().stimulus(observation | {'schema': OLD_VERSION})

    def state(self):
        return super().state() | {'schema': VERSION, 'body_config': asdict(self.body_config)}

    @classmethod
    def restore(cls, state):
        if state['schema'] != VERSION: raise ValueError('developmental world version')
        value = super().restore(state | {'schema': OLD_VERSION})
        value.body_config = BodyConfig(**state['body_config'])
        return value

    def execute_pose(self, pose):
        if pose is None: return np.zeros(4)
        pose = np.asarray(pose, dtype=float)
        if pose.shape != (4,) or not np.isfinite(pose).all() or np.max(np.abs(pose)) > 1:
            raise ValueError('bounded motor pose')
        eye = self.eye_servo(pose[:2]*self.eye_config.angle_limit_rad)
        hand = np.clip(3*(pose[2:]-[self.pointer.x, self.pointer.y])-.9*np.array([self.pointer.vx, self.pointer.vy]), -1, 1)
        return np.concatenate((eye, hand))
