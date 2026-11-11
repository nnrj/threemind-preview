"""A portable population protocol; deliberately independent of Lab services."""

import json
from copy import deepcopy
from typing import Literal

from pydantic import Field, model_validator

from threemind_kernels.registry import BASELINE_KERNEL, resolve_kernel

from .cold_state import StateReference
from .ecology import EcologyCoordinator, EcologySettings
from .population_participant import CoreParticipant, ParticipantConfig
from .profile import profile_from_spec, validate_profile
from .world_schema import Model, WorldSpec, default_world, digest


class EcologyJob(Model):
    schema_id: Literal["threemind.ecology-job/1"] = "threemind.ecology-job/1"
    world: WorldSpec = Field(default_factory=default_world)
    ecology: EcologySettings = Field(default_factory=EcologySettings)
    sensory_seed: int = Field(default=20260724, ge=0, le=2**32 - 1)
    environment_seed: int = Field(default=11, ge=0, le=2**32 - 1)
    core_config: dict = Field(default_factory=dict)
    # Preserve the meaning of older ecology-job/1 JSON with an omitted identity.
    kernel_id: str = BASELINE_KERNEL
    participant: ParticipantConfig = Field(default_factory=ParticipantConfig)
    runtime_profile: dict | None = None

    @model_validator(mode="after")
    def valid(self):
        resolve_kernel(self.kernel_id).configuration(self.core_config)
        self.ecology.validate_world(self.world)
        if self.runtime_profile is not None:
            profile = validate_profile(self.runtime_profile)
            if profile["sensory_seed"] != self.sensory_seed:
                raise ValueError("runtime profile and population sensory seeds differ")
            options = self.participant.model_dump(mode="json")
            for key in set(options) & set(profile):
                if options[key] != profile[key]:
                    raise ValueError(f"participant.{key} must match runtime_profile.{key}")
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))

    @property
    def profile(self):
        if self.runtime_profile is not None:
            return deepcopy(self.runtime_profile)
        return profile_from_spec({"seed": self.sensory_seed, **self.participant.model_dump(mode="json")})

    def open(self, *, backend="native", founders=None, checkpoint=None, record=None, participant_record=None):
        if founders is not None and self.core_config:
            raise ValueError("a founder model owns its Core configuration; core_config applies only to blank founders")

        def factory(identity, image, state):
            reference = image if isinstance(image, StateReference) else None
            if reference is not None:
                image = reference.materialize()
            agent = CoreParticipant(
                identity,
                image,
                self.sensory_seed,
                backend=backend,
                options=self.participant,
                state=state,
                record=(lambda event: participant_record(identity, event)) if participant_record else None,
            )
            if reference is not None and not agent.body_enabled and agent.engine.life == "dead" and agent.dead_recorded:
                agent.archive_engine(reference)
            return agent

        return EcologyCoordinator(
            self.world,
            self.ecology,
            sensory_seed=self.sensory_seed,
            environment_seed=self.environment_seed,
            core_config=self.core_config if founders is None and checkpoint is None else None,
            kernel_id=self.kernel_id,
            founders=founders,
            checkpoint=checkpoint,
            backend=backend,
            participant_factory=factory,
            record=record,
        )


def parse_job(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate ecological protocol field: {key}")
            result[key] = item
        return result

    if isinstance(value, (str, bytes)):
        if len(value.encode() if isinstance(value, str) else value) > 8 * 1024**2:
            raise ValueError("portable ecological protocol exceeds 8 MiB")
        value = json.loads(value, object_pairs_hook=unique)
    encoded = json.dumps(value, allow_nan=False)
    if len(encoded.encode()) > 8 * 1024**2:
        raise ValueError("portable ecological protocol exceeds 8 MiB")
    return EcologyJob.model_validate_json(encoded, strict=True)
