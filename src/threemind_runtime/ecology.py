"""Headless ecological coordination of mutable brains, bodies and resource rules.

The storage host commits checkpoint metadata and all referenced brain images as
one unit. A half-delivered physical interval is explicit, so numerical-step
checkpoints do not pretend every sensor has already reached every brain.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from threemind_kernels.registry import resolve_kernel

from .ecology_rules import EcologyLedger, EcologyRules
from .ecology_senses import BodyStateSenses, transduce
from .inheritance import BIRTH_RULE, KERNEL60, KERNEL60_BIRTH_RULE, birth, birth_metadata, birth_rule
from .population_participant import CoreParticipant, ParticipantConfig
from .population_world import PopulationWorld, SpawnLayout, body_scope
from .world_schema import Id, Model, digest, parse_world


class EcologySettings(Model):
    schema_id: Literal["threemind.ecology/1"] = "threemind.ecology/1"
    root_id: Id = "body"
    founder_count: int = Field(default=2, ge=1, le=256)
    ecology_seed: int = Field(default=20260724, ge=0, le=2**32 - 1)
    body_failure_inputs: Literal["close_all", "detach_body"] = "close_all"
    inheritance_rule: Literal["threemind.birth/1", "threemind.birth/2"] = BIRTH_RULE
    inheritance_decay_age: Literal["preserve", "reset"] | None = None
    rules: EcologyRules = Field(default_factory=EcologyRules)
    senses: BodyStateSenses = Field(default_factory=BodyStateSenses)
    layout: SpawnLayout = Field(default_factory=SpawnLayout)

    @model_validator(mode="after")
    def valid_inheritance(self):
        if self.inheritance_rule == BIRTH_RULE and self.inheritance_decay_age is not None:
            raise ValueError("decay-age inheritance requires threemind.birth/2")
        return self

    @model_serializer(mode="wrap")
    def historical_shape(self, handler):
        value = handler(self)
        # Preserve historical ecology/1 protocol hashes and exact recovery.
        if self.inheritance_decay_age is None:
            value.pop("inheritance_decay_age", None)
        return value

    def birth(self, image):
        return birth(image, rule=self.inheritance_rule, decay_age=self.inheritance_decay_age or "preserve")

    def birth_metadata(self, image):
        return birth_metadata(image, self.inheritance_decay_age or "preserve")

    def for_kernel(self, kernel_id):
        expected = birth_rule(kernel_id)
        if expected == KERNEL60_BIRTH_RULE and self.inheritance_rule == BIRTH_RULE and "inheritance_rule" not in self.model_fields_set:
            return self.model_copy(update={"inheritance_rule": expected})
        if self.inheritance_rule != expected:
            raise ValueError("ecological inheritance rule does not match the selected kernel")
        return self

    def validate_world(self, world):
        if self.founder_count > self.rules.reproduction.population_limit:
            raise ValueError("founder count exceeds the declared population limit")
        if self.rules.reproduction.interval_us % world.physics.sample_us:
            raise ValueError("reproduction interval must contain complete physical sampling intervals")
        body_scope(world, self.root_id)
        self.senses.validate_ports(world)

    @property
    def physical_digest(self):
        value = self.model_dump(mode="json")
        value["rules"] = {"physical_hash": self.rules.physical_digest}
        return digest(value)


class EcologyCoordinator:
    def __init__(
        self,
        world,
        settings=None,
        *,
        sensory_seed=20260724,
        environment_seed=11,
        founders=None,
        core_config=None,
        kernel_id=None,
        participant_options=None,
        backend="native",
        participant_factory=None,
        record=None,
        participant_record=None,
        checkpoint=None,
    ):
        self.world_spec = parse_world(world.model_dump(mode="json") if hasattr(world, "model_dump") else world)
        if settings is None:
            source_kernel = kernel_id
            if founders:
                from threemind_kernels.registry import state_kernel

                source_kernel = state_kernel(founders[0]).kernel_id
            settings = EcologySettings(inheritance_rule=KERNEL60_BIRTH_RULE) if source_kernel == KERNEL60 else EcologySettings()
        if isinstance(settings, dict):
            settings = EcologySettings.model_validate_json(json.dumps(settings))
        if checkpoint is None:
            if founders:
                from threemind_kernels.registry import state_kernel

                for founder in founders:
                    settings = settings.for_kernel(state_kernel(founder).kernel_id)
            elif kernel_id is not None:
                settings = settings.for_kernel(resolve_kernel(kernel_id).kernel_id)
        self.settings = EcologySettings.model_validate_json(
            settings.model_dump_json() if isinstance(settings, EcologySettings) else json.dumps(settings)
        )
        self.settings.validate_world(self.world_spec)
        self.seed, self.environment_seed = sensory_seed, environment_seed
        self.protocol_hash = digest(
            {
                "world": self.world_spec.physical_digest,
                "ecology": self.settings.physical_digest,
                "sensory_seed": sensory_seed,
                "environment_seed": environment_seed,
            }
        )
        self.record = record or (lambda event: None)
        self.participants, self.world = {}, None
        self.time_us, self.pending_end_us, self.pending_events = 0, None, []
        self.failed = False
        options = participant_options or ParticipantConfig()
        self.factory = participant_factory or (
            lambda identity, image, state: CoreParticipant(
                identity,
                image,
                sensory_seed,
                backend=backend,
                options=options,
                state=state,
                record=(lambda event: participant_record(identity, event)) if participant_record else None,
            )
        )
        try:
            context, images = checkpoint if checkpoint is not None else ({}, {})
            if checkpoint is not None:
                if founders is not None or core_config is not None:
                    raise ValueError("resume cannot replace saved brains with founders or new Core configuration")
                if (
                    context.get("schema") != "threemind.ecology-runtime/1"
                    or context.get("protocol_hash") != self.protocol_hash
                ):
                    raise ValueError("ecological protocol changed; exact continuation refused")
                if context.get("checkpoint_hash") != digest(
                    {k: v for k, v in context.items() if k != "checkpoint_hash"}
                ):
                    raise ValueError("ecological checkpoint metadata checksum failed")
                self.time_us = context["time_us"]
                self.pending_end_us = context["pending_end_us"]
                self.pending_events = deepcopy(context["pending_events"])
                if type(self.time_us) is not int or self.time_us < 0:
                    raise ValueError("invalid ecological model clock")
                expected_end = (
                    self.time_us // self.world_spec.physics.sample_us + 1
                ) * self.world_spec.physics.sample_us
                if self.pending_end_us is not None and self.pending_end_us != expected_end:
                    raise ValueError("invalid pending physical delivery boundary")
                if self.pending_end_us is None and (
                    self.time_us % self.world_spec.physics.sample_us or self.pending_events
                ):
                    raise ValueError("missing pending physical interval")
            self.ledger = EcologyLedger(
                self.settings.rules,
                self.settings.ecology_seed,
                self.world_spec.physics.sample_us,
                self.settings.founder_count,
                state=context.get("ledger"),
            )
            self.world = PopulationWorld(
                self.world_spec,
                self.settings.root_id,
                self.settings.rules.reproduction.population_limit,
                sensory_seed,
                environment_seed,
                habitat=self.settings.rules.habitat,
                layout=self.settings.layout,
                state=context.get("world"),
            )
            if checkpoint is not None:
                expected_physics = self.pending_end_us if self.pending_end_us is not None else self.time_us
                if self.world.time_us != expected_physics or self.ledger.time_us != expected_physics:
                    raise ValueError("ecological checkpoint combines incompatible physical and model times")
                if set(images) != set(self.ledger.accounts) or set(context["members"]) != set(images):
                    raise ValueError("ecological checkpoint is missing a brain or lineage member")
                expected_bodies = {key for key, account in self.ledger.accounts.items() if account.alive}
                expected_bodies |= {e["individual"] for e in self.pending_events if e["kind"] == "body_failed"}
                if self.world.members != expected_bodies:
                    raise ValueError("ecological body membership differs from its settlement phase")
                for identity, account in self.ledger.accounts.items():
                    image, member = images[identity], context["members"][identity]
                    if image.digest != member["state_hash"] or account.birth_us > self.time_us:
                        raise ValueError("ecological brain state or birth time mismatch")
                    agent = self.factory(identity, image, member["context"])
                    self.participants[identity] = agent
                    age = self.time_us - account.birth_us
                    if agent.engine.time_us > age or (agent.engine.life != "dead" and agent.engine.time_us != age):
                        raise ValueError("ecological brain clock differs from its recorded birth offset")
            else:
                sources = founders or [resolve_kernel(kernel_id).create(core_config, backend=backend).capture_state()]
                if len(sources) not in (1, self.settings.founder_count):
                    raise ValueError("supply one common founder model or one model for each declared founder")
                for index, identity in enumerate(self.ledger.accounts):
                    source = sources[0 if len(sources) == 1 else index]
                    image = self.settings.birth(source)
                    self.participants[identity] = self.factory(identity, image, None)
                    self.world.activate(identity)
                    self.emit(
                        {
                            "kind": "founder_born",
                            "time_us": 0,
                            "individual": identity,
                            "source_state_hash": source.digest,
                            "state_hash": image.digest,
                            **self.settings.birth_metadata(source),
                            "model_born": True,
                        }
                    )
        except BaseException:
            self.close()
            raise

    def emit(self, event):
        self.record(deepcopy(event))

    def _prepare(self):
        existing = self.world.members
        frames = self.world.step({identity: self.participants[identity].actions() for identity in existing})
        measured = self.world.measurements()
        self.pending_events = self.ledger.step(measured, reproduce=False)
        self.pending_end_us = self.world.time_us
        for identity in sorted(existing):
            port = self.world.port(identity)
            frame, body = transduce(
                self.settings.senses,
                self.world_spec,
                frames[identity],
                self.ledger,
                identity,
                measured[identity]["position"],
                self.seed,
            )
            frame = replace(frame, time_us=frame.time_us - self.ledger.accounts[identity].birth_us)
            self.participants[identity].receive(
                frame,
                {
                    "schema": "threemind.ecological-sample/1",
                    "world_hash": self.world_spec.digest,
                    "ecology_hash": self.settings.physical_digest,
                    "individual": identity,
                    "global_delivery_us": str(self.pending_end_us),
                    "birth_us": str(self.ledger.accounts[identity].birth_us),
                    "physical": measured[identity],
                    "body_state": body,
                    "measurements": deepcopy(port.last_measurements),
                    "controls": deepcopy(port.last_controls),
                },
            )

    def _finish(self):
        for event in self.pending_events:
            if event["kind"] == "body_failed":
                self.world.remove(event["individual"])
                agent = self.participants[event["individual"]]
                agent.body_failed(self.settings.body_failure_inputs)
                agent.advance_to(agent.engine.time_us)  # Record a death actually observed at input closure.
        viable = {key for key, agent in self.participants.items() if agent.engine.life != "dead"}
        decisions = self.ledger.finish_boundary(viable)
        for event in self.pending_events:
            self.emit(event)
        for event in decisions:
            if event["kind"] == "birth_due":
                source = self.participants[event["parent"]].engine.capture_state()
                image = self.settings.birth(source)
                identity = event["individual"]
                self.participants[identity] = self.factory(identity, image, None)
                self.world.activate(identity)
                self.emit(
                    event
                    | {
                        "kind": "individual_born",
                        "model_born": True,
                        "source_time_us": str(self.participants[event["parent"]].engine.time_us),
                        "source_state_hash": source.digest,
                        "state_hash": image.digest,
                        **self.settings.birth_metadata(source),
                    }
                )
            else:
                self.emit(event)
        self.pending_events, self.pending_end_us = [], None

    def advance_to(self, target_us):
        if self.failed:
            raise ValueError("a failed population boundary must be restored from its last complete checkpoint")
        if type(target_us) is not int or not self.time_us <= target_us <= 10**15:
            raise ValueError("invalid ecological target time")
        try:
            while self.time_us < target_us:
                if self.pending_end_us is None:
                    self._prepare()
                target = min(target_us, self.pending_end_us)
                for identity, agent in sorted(self.participants.items()):
                    agent.advance_to(target - self.ledger.accounts[identity].birth_us)
                self.time_us = target
                if self.time_us == self.pending_end_us:
                    self._finish()
        except BaseException:
            self.failed = True
            raise

    def checkpoint(self):
        if self.failed:
            raise ValueError("cannot checkpoint a partially failed population boundary")
        images = {key: agent.engine.capture_state() for key, agent in self.participants.items()}
        metadata = {
            "schema": "threemind.ecology-runtime/1",
            "protocol_hash": self.protocol_hash,
            "time_us": self.time_us,
            "pending_end_us": self.pending_end_us,
            "pending_events": deepcopy(self.pending_events),
            "ledger": self.ledger.snapshot(),
            "world": self.world.capture(),
            "members": {
                key: {"state_hash": images[key].digest, "context": agent.capture()}
                for key, agent in self.participants.items()
            },
        }
        metadata["checkpoint_hash"] = digest(metadata)
        return metadata, images

    def close(self):
        for agent in self.participants.values():
            agent.close()
        self.participants.clear()
        if self.world is not None:
            self.world.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
