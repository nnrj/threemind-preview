"""The registered historical ocean mechanics with genuine native 6.3 individuals."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from types import FunctionType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from lab.tools.ocean import Body, Ocean
from lab.tools.ocean_contact import ContactOcean
from lab.tools.ocean_enclosure import EnclosureOcean
from lab.tools.ocean_evolution import EvolutionOcean
from lab.tools import ocean_species
from threemind_core import StateImage
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth

KERNEL = "threemind.continuous-memory/6.3"
GIB = 2**30


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def newborn_without_endowment(parent):
    if parent.to_dict()["dynamics"] != KERNEL:
        raise ValueError("the 6.3 ocean accepts only 6.3 parents")
    child = birth(parent, rule="threemind.birth/2", decay_age="preserve").to_dict()
    # The ocean parent pays the actual grant. Remove the ordinary free birth
    # endowment from the newborn's energy ledger AND its regional energy pools.
    if child["config"]["energy_initial_reserve"] != 0:
        config = child["config"] | {"energy_initial_reserve": 0.0}
        blank = create_engine(config, kernel_id=KERNEL, backend="native").capture_state().to_dict()
        for field in ("config", "definition", "definition_hash", "energy", "pools", "energy_rng", "energy_serial"):
            child[field] = blank[field]
    if any(n["reserve"] for n in child["nodes"]) or any(v for _, v in child["pools"]):
        raise ValueError("unfunded newborn already has an energy reserve")
    return StateImage.from_dict(child)


def with_funded_birth(original):
    """Bind only the energy-at-birth operation in a private copy of an old function.

    The E28 recorder checks the original apparatus files byte for byte. Keep its
    original modules, globals and functions intact, including in this process.
    """
    assert "zero_energy_birth" in original.__code__.co_names
    namespace = {**original.__globals__, "zero_energy_birth": newborn_without_endowment}
    bound = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    bound.__kwdefaults__ = original.__kwdefaults__
    return bound


class Primitive63(Ocean):
    _reproduce = with_funded_birth(Ocean._reproduce)

    def _founder(self, i, image):
        seed = self.p.seed + i
        if image is None:
            engine = create_engine(self._config(seed), kernel_id=KERNEL, backend=self.backend)
        else:
            engine = create_engine(state=newborn_without_endowment(image), backend=self.backend)
            seed = engine.config.seed
            engine.supply_energy(self.p.initial_energy, time_us=0, source="ocean-founder-endowment/6.3")
            engine.advance_to(0)
        self.seeds[i], self.engines[i] = seed, engine
        self.totals["initial_core"] += self.p.initial_energy
        self.bodies[i] = Body(i, None, 0, 0, self.p.radius_m, self.p.thrust_n, 0.025,
                              self.rng.uniform(0, self.p.side_m, 2).tolist(),
                              [self.p.flow_m_s, 0.0], float(self.rng.uniform(-math.pi, math.pi)))


class Evolution63(EvolutionOcean, Primitive63):
    _reproduce = with_funded_birth(EvolutionOcean._reproduce)


class Contact63(ContactOcean, Evolution63):
    pass


class Enclosure63(EnclosureOcean, Contact63):
    pass


def seed_from_adult(world, candidate):
    manifest = with_funded_birth(ocean_species.seed_founders)(world, candidate.read_bytes(), range(11))
    world.research["species_founders"]["rule"] = "selected by own observed enclosure; threemind.birth/2; decay age preserved; equal endowment"
    return manifest


MATERIAL = ROOT / ".work"
E28_INPUT = MATERIAL / "primitive-ocean-20261003/cases/phase1-0-core/protocol.json"
E30_INPUT = MATERIAL / "ocean-causality-20261003/cases/g0-core/protocol.json"
E37_INPUT = MATERIAL / "ocean-enclosure-20261004/protocol.json"
E38_INPUT = MATERIAL / "ocean-species-20261004/protocol.json"


def primitive(group, mode="core", **updates):
    p = read(E28_INPUT)
    return p | dict(seed=p["seed"] + 100*group, environment_seed=p["environment_seed"] + group, mode=mode) | updates


def contact(group, mode):
    p = read(E30_INPUT)
    p.update(seed=p["seed"] + 100*group, environment_seed=p["environment_seed"] + group)
    if mode == "direct":
        p["core_overrides"] = {"propagation_rate": 0.0, "inhibition_diffusion_rate": 0.0}
    elif mode in ("random", "random-fast"):
        p.update(mode="random", random_interval_us=20000 if mode == "random-fast" else 1000000)
    elif mode != "core":
        raise ValueError(mode)
    return p


def enclosure(source, candidate=None):
    w = Enclosure63(read(source))
    if candidate:
        seed_from_adult(w, candidate)
    w.configure({i: "candidate" if candidate and i < 11 else "other" for i in w.bodies},
                {"candidate": "core", "other": "core"} if candidate else {"other": "core"})
    return w
