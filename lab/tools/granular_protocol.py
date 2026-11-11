"""Validated external-apparatus parameters, separate from consciousness dynamics."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PhysicsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_id: Literal["threemind.granular-transfer-prototype/1"] = Field(
        default="threemind.granular-transfer-prototype/1", alias="schema"
    )
    physics_us: int = Field(default=2000, ge=100, le=10000)
    period_us: int = Field(default=20000, ge=1000, le=1000000)
    camera_interval_us: int = Field(default=100000, ge=1000, le=10000000)
    width: int = Field(default=16, ge=4, le=64)
    height: int = Field(default=12, ge=4, le=64)
    grains: int = Field(default=12, ge=1, le=12)
    grain_radius: Literal[0.003] = 0.003
    force_limits: list[float] = Field(
        default_factory=lambda: [87.0, 87.0, 87.0, 87.0, 12.0, 12.0, 12.0, 60.0], min_length=8, max_length=8
    )
    projection_gain: float = Field(default=0.12, ge=0, le=100, allow_inf_nan=False)
    restock_us: int = Field(default=30000000, ge=1000000, le=3600000000)
    dwell_us: int = Field(default=200000, ge=2000, le=60000000)
    attached: bool = False
    seed: int = Field(default=270001, ge=0, le=2**32 - 1)
    environment_seed: int = Field(default=11, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def intervals_and_limits(self):
        if (
            self.period_us % self.physics_us
            or self.camera_interval_us % self.period_us
            or self.restock_us % self.period_us
        ):
            raise ValueError("control, camera and restock intervals must contain whole physics/control periods")
        if self.dwell_us % self.period_us:
            raise ValueError("dwell interval must contain whole control periods")
        if any(not 0 <= value <= limit for value, limit in zip(self.force_limits, (87, 87, 87, 87, 12, 12, 12, 60))):
            raise ValueError("forces must be finite nonnegative values within the pinned actuator limits")
        return self


class SurvivalProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_id: Literal["threemind.granular-survival/1"] = Field(default="threemind.granular-survival/1", alias="schema")
    world: PhysicsConfig = Field(default_factory=PhysicsConfig)
    core: dict = Field(
        default_factory=lambda: {
            "seed": 270001,
            "energy_simulation_enabled": True,
            "energy_starvation_damage_enabled": True,
            "energy_initial_reserve": 40300.0,
            "energy_capacity": 161200.0,
        }
    )
    food_interval_us: int = Field(default=1000000, ge=1000, le=60000000)
    energy_per_grain: float = Field(default=10100.0, ge=0, le=1e12, allow_inf_nan=False)

    @model_validator(mode="after")
    def core_boundary(self):
        from threemind_kernels.registry import creation_kernel

        parameters = creation_kernel("threemind.continuous-memory/2").configuration(self.core)
        if parameters.seed != self.world.seed:
            raise ValueError("Core and adapter seeds must agree for this protocol")
        if not parameters.energy_simulation_enabled:
            raise ValueError("survival task requires explicit finite energy accounting")
        if self.food_interval_us % self.world.period_us:
            raise ValueError("food interval must contain whole control periods")
        return self
