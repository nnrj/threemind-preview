"""Optional head-fixed physical reference for the /4 eye, without Core changes.

The nose is a small sphere in head coordinates. Analytic ray/sphere intersection
uses the same subrays as scene rendering. It is neither a label nor a reticle.
"""
from dataclasses import asdict
import numpy as np
import mujoco
from lab.tools.active_eye import ActiveEyeClassroom, EyeConfig, VERSION as PREVIOUS
from lab.tools.shape_color_world import Pointer

VERSION = 'threemind.grounded-classroom/5'


class EyeHandWorld(ActiveEyeClassroom):
    def __init__(self, seed=91, weather_seed=47, *, config=None, visible_self=True, nose=False):
        self.nose = bool(nose)
        super().__init__(seed, weather_seed, config=config, visible_self=visible_self)

    def nose_geometry(self):
        forward = -self.origin / np.linalg.norm(self.origin)
        right = np.array([1., 0., 0.]); up = np.cross(right, forward)
        return self.origin + .18*forward + .04*right - .05*up, .012

    def vision(self):
        if not self.nose:
            return super().vision()
        self._refresh_directions()
        self.model.geom_pos[self.self_id] = [self.pointer.x, self.pointer.y, .4] if self.visible_self else [0, 0, -10]
        self.model.geom_pos[self.teacher_id] = [*self.marker, .52] if self.marker is not None else [0, 0, -10]
        mujoco.mj_forward(self.model, self.data)
        center, radius = self.nose_geometry(); offset = self.origin-center
        samples = []; geom = np.array([-1], dtype=np.int32)
        for directions in self._subdirections:
            values = []
            for direction in directions:
                distance = float(mujoco.mj_ray(self.model, self.data, self.origin, direction, None, 1, -1, geom))
                rgb = self.model.geom_rgba[geom[0], :3].tolist() if geom[0] >= 0 else [0., 0., 0.]
                b = float(offset@direction); disc = b*b-float(offset@offset)+radius*radius
                hit = -b-np.sqrt(disc) if disc >= 0 else -1.
                if hit > 0 and (distance < 0 or hit < distance):
                    distance, rgb = float(hit), [.75, .50, .35]
                values.append([0. if distance < 0 else 1/(1+distance), *rgb])
            samples.append(np.mean(values, axis=0))
        return {'values': np.asarray(samples).ravel().tolist()}

    def observe(self, *, motor_only=False):
        return super().observe(motor_only=motor_only) | {'schema': VERSION, 'nose': self.nose}

    def stimulus(self, observation):
        if observation['schema'] != VERSION:
            raise ValueError('eye/hand world /5 observation required')
        return super().stimulus(observation | {'schema': PREVIOUS})

    def state(self):
        return super().state() | {'schema': VERSION, 'nose': self.nose}

    @classmethod
    def restore(cls, state):
        if state['schema'] != VERSION:
            raise ValueError('eye/hand world /5 state required')
        w = cls(state['seed'], state['weather_seed'], config=EyeConfig(**state['eye_config']),
                visible_self=state['visible_self'], nose=state['nose'])
        w.set_scene(state['items'], state['variant'], state['positions'])
        w.pointer = Pointer(**state['pointer'])
        for key in ('marker', 'time_s', 'body_temperature', 'acceleration', 'motor_power', 'contact_force', 'eye_power'):
            setattr(w, key, state[key])
        w.eye_angle = np.array(state['eye_angle']); w.eye_velocity = np.array(state['eye_velocity'])
        w._refresh_directions()
        return w


def teacher_eye_angle(world, xy, z=.16):
    """External demonstration/scoring only; never a learned-controller input."""
    direction = np.array([*xy, z])-world.origin
    base = -world.origin/np.linalg.norm(world.origin)
    right = np.array([1., 0., 0.]); up = np.cross(right, base)
    return np.array([np.arctan2(direction@right, direction@base),
                     np.arctan2(direction@up, np.hypot(direction@right, direction@base))])


def motor_metrics(rows, eye_targets, hand_targets, dt=.05):
    """Process metrics. No minimum dwell is imposed on the actual controller."""
    if len(rows) != len(eye_targets) or len(rows) != len(hand_targets) or not rows:
        raise ValueError('aligned actual observations and external scoring targets')
    eye = np.array([r['observation']['eye_angle_rad'] for r in rows])
    speed = np.linalg.norm([r['observation']['eye_velocity_rad_s'] for r in rows], axis=1)
    hand = np.array([[r['observation']['pointer'][k] for k in ('x', 'y')] for r in rows])
    error = np.linalg.norm(eye-np.asarray(eye_targets), axis=1)
    target = np.asarray(eye_targets)
    direction = np.column_stack((np.sin(target[:, 0])*np.cos(target[:, 1]),
                                 np.sin(target[:, 1]), np.cos(target[:, 0])*np.cos(target[:, 1])))
    yaw, pitch = eye[:, 0], eye[:, 1]
    forward = np.column_stack((np.sin(yaw)*np.cos(pitch), np.sin(pitch), np.cos(yaw)*np.cos(pitch)))
    right = np.column_stack((np.cos(yaw), np.zeros(len(eye)), -np.sin(yaw)))
    up = np.column_stack((-np.sin(yaw)*np.sin(pitch), np.cos(pitch), -np.cos(yaw)*np.sin(pitch)))
    depth = np.sum(direction*forward, axis=1)
    uv = np.column_stack((np.sum(direction*right, axis=1), np.sum(direction*up, axis=1)))/depth[:, None]
    center = (depth > 0) & (np.max(np.abs(uv), axis=1) <= .075)
    stable = center & (speed < .08)
    distance = np.linalg.norm(hand-np.asarray(hand_targets), axis=1)
    longest = current = 0
    for ok in stable:
        current = current+1 if ok else 0; longest = max(longest, current)
    return {'eye_mean_error_rad': float(error.mean()), 'eye_center_fraction': float(center.mean()),
            'eye_stable_fraction': float(stable.mean()), 'eye_longest_stable_s': longest*dt,
            'eye_mean_speed_rad_s': float(speed.mean()), 'hand_mean_distance_m': float(distance.mean()),
            'hand_arrived_fraction': float(np.mean(distance <= .20)),
            'eye_final_error_rad': float(error[-1]), 'hand_final_distance_m': float(distance[-1])}
