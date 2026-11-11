"""E27 prototype: actual contacts, free vessels and unlabelled visual measurements.

No Core imports or access. This prototype is frozen with experimental evidence
before extracting a reusable adapter. All task judgements stay external.
"""

import copy
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco as mj
import numpy as np

from threemind_runtime.adapters import channel_id
from threemind_runtime.playground_assets import manifest, root, valid


def assets():
    destination = root()
    source = Path('.work/playground-menagerie').resolve()
    for item in manifest()['asset_files']:
        target = destination / item['path']
        if valid(target, item):
            continue
        original = source / item['path']
        if valid(original, item):
            data = original.read_bytes()
        else:
            # Windows checkouts may normalize LF. Read the pinned Git blob,
            # never accept altered bytes or change the scientific manifest.
            data = subprocess.run(['git', '-C', str(source), 'show',
                manifest()['menagerie_revision']+':'+item['path']],
                check=True, capture_output=True).stdout
            if len(data) != item['bytes'] or hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest() != item['git_blob']:
                raise ValueError('Pinned Panda assets unavailable: ' + item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return destination / 'franka_emika_panda'


def numbers(values):
    return ' '.join(format(float(v), '.17g') for v in values)


def cup(parent, name, position, halfwidth, height, color, *, free=True):
    body = ET.SubElement(parent, 'body', name=name, pos=numbers(position))
    if free:
        ET.SubElement(body, 'freejoint', name=name + '_joint')
    thickness = .003
    parts = [('base', (halfwidth, halfwidth, thickness), (0, 0, -height / 2))]
    for axis in (0, 1):
        for side in (-1, 1):
            size, offset = [halfwidth, halfwidth, height / 2], [0., 0., 0.]
            size[axis] = thickness
            offset[axis] = side * halfwidth
            parts.append((f'wall{axis}_{side}', size, offset))
    for label, size, offset in parts:
        ET.SubElement(body, 'geom', name=f'{name}_{label}', type='box', size=numbers(size),
                      pos=numbers(offset), density='400', friction='1.2 .005 .0001',
                      rgba=numbers(color), solref='.004 1')
    return body


def make_xml(folder, cfg):
    tree = ET.parse(folder / 'panda.xml').getroot()
    tree.find('compiler').set('meshdir', str(folder / 'assets'))
    option = tree.find('option')
    option.set('timestep', str(cfg['physics_us'] / 1e6))
    option.set('gravity', '0 0 -9.81')
    option.set('iterations', '100')
    # Keep physical forces, masses, joint limits and coupling; replace upstream
    # position servos with explicit raw force/torque actuators, including tendon.
    for index, actuator in enumerate(tree.find('actuator')):
        limit = cfg['force_limits'][index]
        actuator.set('gaintype', 'fixed')
        actuator.set('biastype', 'none')
        actuator.set('gainprm', '1')
        actuator.set('biasprm', '0 0 0')
        actuator.set('ctrlrange', f'{-limit} {limit}')
        actuator.set('forcerange', f'{-limit} {limit}')
    tree.remove(tree.find('keyframe'))  # New free objects need a new initial state.
    world = tree.find('worldbody')
    ET.SubElement(world, 'geom', name='ground', type='plane', size='2 2 .01', rgba='.25 .3 .3 1')
    ET.SubElement(world, 'geom', name='table', type='box', pos='.49 0 .04', size='.28 .35 .04',
                  rgba='.45 .36 .25 1', friction='1 .005 .0001')
    ET.SubElement(world, 'light', name='lamp', pos='.2 -.3 1.5', dir='0 0 -1', diffuse='.8 .8 .8')
    source = cup(world, 'source', (.4, -.10, .114), .027, .06, (.2, .65, .75, 1))
    cup(world, 'receiver', (.54, .13, .124), .05, .08, (.8, .58, .22, 1))
    for i in range(cfg['grains']):
        body = ET.SubElement(world, 'body', name=f'grain{i}', pos=numbers((.394 + (i % 3)*.006,
                            -.106 + ((i//3) % 3)*.006, .103+(i//9)*.007)))
        ET.SubElement(body, 'freejoint', name=f'grain{i}_joint')
        ET.SubElement(body, 'geom', name=f'grain{i}', type='sphere', size=str(cfg['grain_radius']),
                      density='1200', friction='.35 .003 .0001', rgba='.9 .2 .3 1', solref='.004 1')
    hand = world.find(".//body[@name='hand']")
    ET.SubElement(hand, 'site', name='grasp', pos='0 0 .103', size='.002', rgba='0 0 0 0')
    ET.SubElement(hand, 'site', name='imu', size='.002', rgba='0 0 0 0')
    sensors = ET.SubElement(tree, 'sensor')
    ET.SubElement(sensors, 'accelerometer', name='acceleration', site='imu')
    ET.SubElement(sensors, 'gyro', name='gyro', site='imu')
    position, look = np.array([.62, -.66, .56]), np.array([.46, .04, .15])
    z = position-look
    z /= np.linalg.norm(z)
    x = np.cross([0., 0., 1.], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    ET.SubElement(world, 'camera', name='observer', pos=numbers(position), xyaxes=numbers([*x, *y]), fovy='48')
    if cfg['attached']:
        # Secondary, explicitly different task. Never enabled for free-cup founders.
        source.remove(source.find('freejoint'))
        world.remove(source)
        source.set('pos', '0 0 .103')
        source.set('quat', '0 1 0 0')
        hand.append(source)
    return ET.tostring(tree, encoding='unicode')


def defaults():
    return dict(schema='threemind.granular-transfer-prototype/1', physics_us=2000, period_us=20000,
                camera_interval_us=100000, width=16, height=12, grains=12, grain_radius=.003,
                force_limits=[87.,87.,87.,87.,12.,12.,12.,60.], projection_gain=.12,
                restock_us=30000000, dwell_us=200000, attached=False, seed=270001, environment_seed=11)


class TransferWorld:
    def __init__(self, config=None, state=None):
        self.cfg = defaults() | (config or {})
        self.xml = make_xml(assets(), self.cfg)
        self.model = mj.MjModel.from_xml_string(self.xml)
        self.data = mj.MjData(self.model)
        self.xml_hash = hashlib.sha256(self.xml.encode()).hexdigest()
        self.protocol_hash = hashlib.sha256(json.dumps(self.cfg, sort_keys=True).encode()).hexdigest()
        self.mask = int(mj.mjtState.mjSTATE_INTEGRATION)
        self.joints = [self.model.joint(f'joint{i}') for i in range(1,8)]
        self.finger_joints = [self.model.joint(f'finger_joint{i}') for i in (1,2)]
        self.robot_q = np.array([j.qposadr[0] for j in self.joints])
        self.robot_d = np.array([j.dofadr[0] for j in self.joints])
        self.finger_d = [int(j.dofadr[0]) for j in self.finger_joints]
        self.data.qpos[self.robot_q] = [0.,-.35,0.,-2.,0.,1.65,.785398]
        for j in self.finger_joints:
            self.data.qpos[j.qposadr[0]] = .04
        mj.mj_forward(self.model, self.data)
        self.site = self.model.site('grasp').id
        self.hand = self.model.body('hand').id
        self.left = self.model.body('left_finger').id
        self.right = self.model.body('right_finger').id
        self.source = self.model.body('source').id
        self.receiver = self.model.body('receiver').id
        self.time_us, self.batch = 0, -1
        self.next_camera_us = 0
        self.last_visual = []
        self.pending = {}
        self.paid = set()
        self.spilled_ids, self.spill_pending = set(), {}
        self.ever_grasped, self.ever_lifted = False, False
        self.grasp_contact_us = 0
        self.transferred = self.spilled = 0
        self.work_j, self.peak_contact_n = 0., 0.
        self.contacts = [0.,0.,0.]
        self.events = []
        self.projection = {}
        self.renderer = mj.Renderer(self.model, height=self.cfg['height'], width=self.cfg['width'])
        if state is None:
            self.restock()
        else:
            self.restore(state)

    def free_pose(self, name, position, quaternion=(1.,0.,0.,0.)):
        j = self.model.joint(name+'_joint')
        self.data.qpos[j.qposadr[0]:j.qposadr[0]+7] = [*position,*quaternion]
        self.data.qvel[j.dofadr[0]:j.dofadr[0]+6] = 0

    def restock(self):
        self.batch += 1
        rng = np.random.default_rng(np.random.SeedSequence([self.cfg['environment_seed'], self.batch]))
        self.source_start = np.array([.4+rng.uniform(-.015,.015), -.10+rng.uniform(-.015,.015), .114])
        self.receiver_start = np.array([.54+rng.uniform(-.02,.02), .13+rng.uniform(-.025,.025), .124])
        if not self.cfg['attached']:
            self.free_pose('source', self.source_start)
        self.free_pose('receiver', self.receiver_start)
        mj.mj_forward(self.model, self.data)
        rotation, center = self.data.xmat[self.source].reshape(3,3), self.data.xpos[self.source].copy()
        for i in range(self.cfg['grains']):
            offset = np.array([-.007+(i%3)*.007, -.007+((i//3)%3)*.007, -.017+(i//9)*.007])
            self.free_pose(f'grain{i}', center+rotation@offset)
        mj.mj_forward(self.model,self.data)
        self.pending, self.paid = {}, set()
        self.spilled_ids, self.spill_pending = set(), {}
        self.ever_grasped = self.ever_lifted = bool(self.cfg['attached'])
        self.grasp_contact_us = 0
        self.events.append(dict(kind='external_restock',time_us=self.time_us,batch=self.batch,
                                source=self.source_start.tolist(),receiver=self.receiver_start.tolist()))

    def action(self, activations):
        values = sorted((int(n),float(a)) for n,a in activations)
        cache = {n:self.projection.get(n) or tuple(1 if channel_id(self.cfg['seed'],f'granular-motor/1:{i}',n)&1 else -1
                    for i in range(8)) for n,_ in values}
        result = [math.tanh(self.cfg['projection_gain']*math.fsum(cache[n][i]*a for n,a in values)) for i in range(8)]
        self.projection = cache
        return result

    def step(self, action):
        if len(action)!=8 or any(not math.isfinite(v) or abs(v)>1 for v in action):
            raise ValueError('Eight normalized finite raw-torque actions are required')
        if self.time_us and self.time_us % self.cfg['restock_us'] == 0:
            self.restock()
        self.data.ctrl[:] = np.asarray(action)*self.cfg['force_limits']
        contact = np.zeros(3)
        wrench = np.empty(6)
        for _ in range(self.cfg['period_us']//self.cfg['physics_us']):
            mj.mj_step(self.model,self.data)
            self.work_j += float(np.sum(np.abs(self.data.actuator_force*self.data.actuator_velocity)))*self.cfg['physics_us']/1e6
            both = set()
            for idx in range(self.data.ncon):
                c = self.data.contact[idx]
                bodies = set(int(self.model.geom_bodyid[g]) for g in c.geom)
                mj.mj_contactForce(self.model,self.data,idx,wrench)
                force = float(np.linalg.norm(wrench[:3]))
                self.peak_contact_n = max(self.peak_contact_n,force)
                for k,b in enumerate((self.left,self.right,self.source)):
                    if b in bodies: contact[k] = max(contact[k],force)
                if self.source in bodies and force > .001:
                    both.update(bodies & {self.left,self.right})
            self.grasp_contact_us = self.grasp_contact_us+self.cfg['physics_us'] if len(both)==2 else 0
            if self.grasp_contact_us >= 100000 and not self.ever_grasped:
                self.ever_grasped = True
                self.events.append(dict(kind='physical_grasp',time_us=round(self.data.time*1e6),batch=self.batch))
        self.time_us += self.cfg['period_us']
        mj.mj_forward(self.model,self.data)
        self.contacts = contact.tolist()
        if not np.isfinite(self.data.qpos).all() or any(w.number for w in self.data.warning):
            raise RuntimeError('Physics warning/nonfinite state; preserve failed trial')
        if self.ever_grasped and self.data.xpos[self.source,2] > self.source_start[2]+.04 and not self.ever_lifted:
            self.ever_lifted = True
            self.events.append(dict(kind='physical_lift',time_us=self.time_us,batch=self.batch))
        earned = 0
        r = self.data.xmat[self.receiver].reshape(3,3)
        center = self.data.xpos[self.receiver]
        for i in range(self.cfg['grains']):
            if i in self.paid: continue
            p = self.data.body(f'grain{i}').xpos
            local = r.T@(p-center)
            # Interior floor is -0.037 m. Include sphere radius and physical
            # contact penetration tolerance instead of excluding resting grains.
            inside = abs(local[0]) < .046 and abs(local[1]) < .046 and -.038 < local[2] < .04 and r[2,2]>.5
            if inside and self.ever_lifted:
                self.pending.setdefault(i,self.time_us)
                if self.time_us-self.pending[i]>=self.cfg['dwell_us']:
                    self.paid.add(i)
                    earned += 1
                    self.transferred += 1
                    self.events.append(dict(kind='qualified_transfer',time_us=self.time_us,batch=self.batch,grain=i))
            else:
                self.pending.pop(i,None)
            s_local = self.data.xmat[self.source].reshape(3,3).T@(p-self.data.xpos[self.source])
            in_source = abs(s_local[0])<.03 and abs(s_local[1])<.03 and -.032<s_local[2]<.034
            j = self.model.joint(f'grain{i}_joint')
            speed = float(np.linalg.norm(self.data.qvel[j.dofadr[0]:j.dofadr[0]+3]))
            if not inside and not in_source and p[2]<.09 and speed<.03 and i not in self.spilled_ids:
                self.spill_pending.setdefault(i,self.time_us)
                if self.time_us-self.spill_pending[i]>=self.cfg['dwell_us']:
                    self.spilled_ids.add(i)
                    self.spilled += 1
                    self.events.append(dict(kind='settled_spill',time_us=self.time_us,batch=self.batch,grain=i))
            else:
                self.spill_pending.pop(i,None)
        return earned

    def senses(self, reserve_fraction=0.):
        # A new external mapping version; never alters existing world/text maps.
        raw = [float(self.data.qpos[j.qposadr[0]]) for j in self.joints+self.finger_joints]
        raw += [float(self.data.qvel[j.dofadr[0]]) for j in self.joints+self.finger_joints]
        raw += self.contacts
        raw += self.data.sensor('acceleration').data.tolist()+self.data.sensor('gyro').data.tolist()
        raw += [reserve_fraction]
        scales = [3.]*7+[.04]*2+[5.]*9+[20.]*3+[9.81]*3+[3.]*3+[1.]
        channels = []
        mask = channel_id(self.cfg['seed'],'granular-senses/1',0)
        for i,(v,scale) in enumerate(zip(raw,scales)):
            value = math.tanh(v/scale)
            if value: channels.append((((i<<12)|int(v<0))^mask,abs(value)))
        visual = None
        if self.time_us >= self.next_camera_us:
            self.renderer.update_scene(self.data,camera='observer')
            rgb = self.renderer.render().copy()
            # Fixed photometric conversion, no object detector/segmentation labels.
            gray = np.rint(rgb.astype(float)@np.array([.2126,.7152,.0722])).astype(np.uint8)
            visual = gray.reshape(-1).tolist()
            self.last_visual = visual
            channels += [(((100<<12)|i)^mask,float(v)/255) for i,v in enumerate(visual) if v]
            self.next_camera_us = self.time_us+self.cfg['camera_interval_us']
        return tuple(sorted(channels)),dict(physical=raw,scales=scales,luminance=visual,
                                            width=self.cfg['width'],height=self.cfg['height'])

    def capture(self):
        integration = np.empty(mj.mj_stateSize(self.model,self.mask))
        mj.mj_getState(self.model,self.data,integration,self.mask)
        return dict(schema='threemind.granular-world-state/1',config=copy.deepcopy(self.cfg),xml_hash=self.xml_hash,
                    mujoco=mj.__version__,integration=integration.tolist(),time_us=self.time_us,batch=self.batch,
                    next_camera_us=self.next_camera_us,last_visual=self.last_visual,
                    pending={str(k):v for k,v in self.pending.items()},paid=sorted(self.paid),
                    spilled_ids=sorted(self.spilled_ids),spill_pending={str(k):v for k,v in self.spill_pending.items()},
                    events=copy.deepcopy(self.events),
                    ever_grasped=self.ever_grasped,ever_lifted=self.ever_lifted,grasp_contact_us=self.grasp_contact_us,
                    transferred=self.transferred,spilled=self.spilled,work_j=self.work_j,peak_contact_n=self.peak_contact_n,
                    contacts=self.contacts,source_start=self.source_start.tolist(),receiver_start=self.receiver_start.tolist())

    def restore(self,s):
        if s['config']!=self.cfg or s['xml_hash']!=self.xml_hash or s['mujoco']!=mj.__version__:
            raise ValueError('Physical protocol/version changed')
        a = np.asarray(s['integration'])
        mj.mj_setState(self.model,self.data,a,self.mask)
        mj.mj_forward(self.model,self.data)
        mj.mj_setState(self.model,self.data,a,self.mask)
        for k in ('time_us','batch','next_camera_us','last_visual','ever_grasped','ever_lifted','grasp_contact_us',
                  'transferred','spilled','work_j','peak_contact_n','contacts'):
            setattr(self,k,copy.deepcopy(s[k]))
        self.pending={int(k):v for k,v in s['pending'].items()}
        self.paid=set(s['paid'])
        self.spilled_ids=set(s['spilled_ids'])
        self.spill_pending={int(k):v for k,v in s['spill_pending'].items()}
        self.events=copy.deepcopy(s['events'])
        self.source_start=np.asarray(s['source_start'])
        self.receiver_start=np.asarray(s['receiver_start'])

    def close(self):
        self.renderer.close()

    def __enter__(self): return self
    def __exit__(self,*_): self.close()


def engineering_action(world, position, rotation, opening):
    """Privileged feasibility controller ONLY. Never an input/demonstration to Core."""
    m,d = world.model,world.data
    jp,jr = np.zeros((3,m.nv)),np.zeros((3,m.nv))
    mj.mj_jacSite(m,d,jp,jr,world.site)
    current=d.site_xmat[world.site].reshape(3,3)
    orientation=.5*sum((np.cross(current[:,i],rotation[:,i]) for i in range(3)),np.zeros(3))
    jac=np.vstack([jp[:,world.robot_d],jr[:,world.robot_d]])
    error=np.concatenate([np.asarray(position)-d.site_xpos[world.site],orientation])
    delta=jac.T@np.linalg.solve(jac@jac.T+.003*np.eye(6),error)
    goal=d.qpos[world.robot_q]+np.clip(delta,-.1,.1)
    limits=m.jnt_range[[j.id for j in world.joints]]
    goal=np.clip(goal,limits[:,0]+.005,limits[:,1]-.005)
    torque=np.array([250,250,250,200,100,100,50])*(goal-d.qpos[world.robot_q])-np.array([25,25,25,20,5,5,2])*d.qvel[world.robot_d]+d.qfrc_bias[world.robot_d]
    finger=float(d.qpos[world.finger_joints[0].qposadr[0]])
    hand_force=1000*(opening-finger)-20*float(d.qvel[world.finger_d[0]])
    return np.clip(np.concatenate([torque,[hand_force]])/world.cfg['force_limits'],-1,1).tolist()
