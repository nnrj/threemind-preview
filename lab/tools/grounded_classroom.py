"""A physical background for the classroom, outside the consciousness kernel.

The fan and weather are prescribed environment conditions. They act on the
carriage and its temperature before being measured; none depends on a lesson,
answer, Core state or researcher CPU load. Version 1 classrooms are untouched.
"""
from dataclasses import asdict
import math
import numpy as np
from threemind_core import Stimulus
from lab.tools.shape_color_world import ShapeColorWorld, Pointer, VERSION as BASE_VERSION

VERSION = 'threemind.grounded-classroom/1'
FIELDS = ('wind_x_m_s', 'wind_y_m_s', 'air_temperature_K', 'relative_humidity',
          'body_temperature_K', 'acceleration_x_m_s2', 'acceleration_y_m_s2',
          'specific_force_z_m_s2', 'support_force_N', 'motor_power_W')
SCALES = (2., 2., 300., 1., 310., 10., 10., 10., 10., 8.)


class GroundedClassroom(ShapeColorWorld):
    def __init__(self, seed=91, weather_seed=47):
        super().__init__(seed)
        self.weather_seed = int(weather_seed)
        self.body_temperature = 295.
        self.acceleration = [0., 0.]
        self.motor_power = 0.

    @property
    def channels(self):
        return super().channels + tuple(self.wiring.identity(0xE10000+i) for i in range(20))

    def weather(self):
        t, phase = self.time_s, self.weather_seed * .17
        return (.6*math.sin(t/7+phase)+.2*math.cos(t/3),
                .5*math.cos(t/11+phase), 293.15+3*math.sin(t/31+phase),
                .55+.15*math.sin(t/43+phase))

    def advance_physics(self, action=(0., 0.), dt=.05):
        action = np.asarray(action, dtype=float)
        if action.shape != (2,) or not np.isfinite(action).all() or not 0 < dt <= .1:
            raise ValueError('finite two-axis forces and bounded physical step')
        wx, wy, air, _ = self.weather()
        old = np.array([self.pointer.vx, self.pointer.vy])
        force = 4*np.clip(action, -1, 1)
        velocity = old + dt*(force - 3*old + .15*(np.array([wx, wy])-old))
        velocity = np.clip(velocity, -1, 1)
        position = np.array([self.pointer.x, self.pointer.y]) + dt*velocity
        hit = np.abs(position) > 1
        position = np.clip(position, -1, 1); velocity[hit] = 0.
        self.acceleration = ((velocity-old)/dt).tolist()
        self.pointer = Pointer(*map(float, position), *map(float, velocity))
        self.motor_power = float(np.sum(np.abs(force*velocity)))
        # A thermal body with heat capacity 20 J/K, exchange 0.4 W/K and
        # measured actuator losses. No temperature labels or energy reward.
        self.body_temperature += dt*(.4*(air-self.body_temperature)+.2*self.motor_power)/20
        self.time_s += dt

    def observe(self, *, motor_only=False):
        base = super().observe(motor_only=motor_only)
        wx, wy, air, humidity = self.weather()
        raw = (wx, wy, air, humidity, self.body_temperature, *self.acceleration, 9.81, 9.81, self.motor_power)
        encoded = []
        for value, scale in zip(raw, SCALES):
            encoded.extend((max(0., value/scale), max(0., -value/scale)))
        return base | {'schema': VERSION, 'values': base['values']+encoded,
                       'physical_background': dict(zip(FIELDS, raw)),
                       'physical_scales': dict(zip(FIELDS, SCALES)),
                       'background_gain_per_signed_channel': .02}

    def stimulus(self, observation):
        if observation['schema'] != VERSION or len(observation['values']) != 292:
            raise ValueError('grounded classroom observation schema')
        values = np.asarray(observation['values'], dtype=float)
        if not np.isfinite(values).all() or np.min(values) < 0:
            raise ValueError('finite nonnegative sensory values')
        gains = [.03]*256 + [.5]*16 + [.02]*20
        return Stimulus(0, tuple((c, float(v*g)) for c,v,g in zip(self.channels,values,gains) if v > 0), intensity=1.)

    def state(self):
        return super().state() | {'schema': VERSION, 'weather_seed': self.weather_seed,
                'body_temperature': self.body_temperature, 'acceleration': self.acceleration,
                'motor_power': self.motor_power}

    @classmethod
    def restore(cls, state):
        if state['schema'] != VERSION: raise ValueError('grounded world version')
        w = cls(state['seed'], state['weather_seed'])
        w.set_scene(state['items'], state['variant']); w.pointer = Pointer(**state['pointer'])
        for name in ('marker', 'time_s', 'body_temperature', 'acceleration', 'motor_power'):
            setattr(w, name, state[name])
        return w
