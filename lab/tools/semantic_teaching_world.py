"""Cross color with shape so one property cannot identify every referent.

Uses the same ray measurement and anonymous wiring as TeachingWorld. Object
names and properties belong to the teacher, never to the sensory payload.
"""

import mujoco

from lab.tools.language_teaching_world import TeachingWorld
from threemind_runtime.receptors import ReceptorWiring

WORDS = ("红球", "蓝球", "红盒", "蓝盒")
COLORS = ("红色", "蓝色", "红色", "蓝色")
SHAPES = ("球", "球", "盒", "盒")


class SemanticTeachingWorld(TeachingWorld):
    def __init__(self, seed=17):
        self.wiring = ReceptorWiring(seed)
        bodies = []
        for item, (x, y) in enumerate(((-.6, -.6), (.6, -.6), (-.6, .6), (.6, .6))):
            kind, size = ("sphere", ".12") if item < 2 else ("box", ".12 .12 .12")
            color = "1 .1 .1 1" if item % 2 == 0 else ".1 .1 1 1"
            bodies.append(f'<body pos="{x} {y} .15"><freejoint/><geom type="{kind}" size="{size}" mass=".1" rgba="{color}"/></body>')
        self.model = mujoco.MjModel.from_xml_string(
            '<mujoco><option timestep=".005" gravity="0 0 -9.81"/><worldbody>'
            '<geom type="plane" size="4 4 .1" rgba=".4 .4 .4 1"/>' + ''.join(bodies) + '</worldbody></mujoco>'
        )
        self.data = mujoco.MjData(self.model)
        for _ in range(200):
            mujoco.mj_step(self.model, self.data)
