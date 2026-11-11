"""Reusable external loop: physical outcome -> timed food -> existing energy port."""

import copy

from threemind_core import Stimulus
from threemind_runtime import create_engine

from .granular_physics import TransferWorld
from .granular_protocol import SurvivalProtocol


class SurvivalSession:
    def __init__(self, protocol, *, image=None, context=None, backend="native"):
        SurvivalProtocol.model_validate(protocol)
        self.protocol = copy.deepcopy(protocol)
        self.engine = create_engine(
            protocol["core"] if image is None else None,
            state=image,
            kernel_id="threemind.continuous-memory/2",
            backend=backend,
        )
        self.world = TransferWorld(protocol["world"], context["world"] if context else None)
        self.pending_food = float(context["pending_food"]) if context else 0.0
        self.next_food_us = int(context["next_food_us"]) if context else protocol["food_interval_us"]
        self.offered = float(context["offered"]) if context else 0.0
        if context and context["protocol"] != protocol:
            self.close()
            raise ValueError("Survival protocol changed during continuation")
        if self.engine.life != "dead" and self.engine.time_us != self.world.time_us:
            self.close()
            raise ValueError("Physical and Core clocks differ")

    def step(self, record=None, *, action=None):
        if self.engine.life == "dead":
            raise ValueError("A dead individual cannot resume or reproduce as a survivor")
        before = self.engine.metrics()
        activation = self.engine.activations()
        selected = self.world.action(activation) if action is None else action
        grains = self.world.step(selected)
        when = self.world.time_us
        self.pending_food += grains * self.protocol["energy_per_grain"]
        delivery = None
        if when >= self.next_food_us:
            if self.pending_food > 0:
                delivery = {"amount": self.pending_food, "time_us": when, "source": "physical-grain-transfer/1"}
                delivery["event_id"] = self.engine.supply_energy(
                    self.pending_food, time_us=when, source=delivery["source"]
                )
                self.offered += self.pending_food
                self.pending_food = 0.0
            self.next_food_us += self.protocol["food_interval_us"]
        energy = before["energy"]
        capacity = self.engine.config.energy_capacity
        channels, physical = self.world.senses(energy["reserve"] / capacity if capacity else 0.0)
        stimulus = Stimulus(when, channels)
        event_id = self.engine.inject(stimulus)
        self.engine.advance_to(when)
        events, self.world.events = self.world.events, []
        if record:
            record(
                {
                    "time_us": when,
                    "action": selected,
                    "stimulus": stimulus.to_dict(),
                    "core_event_id": event_id,
                    "physical": physical,
                    "world_events": events,
                    "food": delivery,
                    "activations_before": activation,
                }
            )
        return grains

    def metrics(self):
        w = self.world
        return {
            "core": self.engine.metrics(),
            "time_us": w.time_us,
            "transferred": w.transferred,
            "spilled": w.spilled,
            "batch": w.batch,
            "grasped": w.ever_grasped,
            "lifted": w.ever_lifted,
            "mechanical_work_j": w.work_j,
            "peak_contact_n": w.peak_contact_n,
            "pending_food": self.pending_food,
            "offered": self.offered,
            "physical_site": w.data.site_xpos[w.site].tolist(),
            "source": w.data.xpos[w.source].tolist(),
        }

    def context(self):
        return {
            "schema": "threemind.granular-survival-session/1",
            "protocol": copy.deepcopy(self.protocol),
            "world": self.world.capture(),
            "pending_food": self.pending_food,
            "next_food_us": self.next_food_us,
            "offered": self.offered,
        }

    def close(self):
        self.world.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
