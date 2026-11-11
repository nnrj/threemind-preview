"""External sensory carriers. Only anonymous Stimulus values reach Core.

Units are never merged by timestamp. Metadata describes the measurement, not
what it should mean to the model. No topology access or semantic routing.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from threemind_core import Stimulus
from threemind_core.spec import timestamp

VERSION = "threemind.stimulus-unit/1"


class Element(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    channel: int = Field(ge=0, le=2**32 - 1)
    value: float = Field(ge=0, le=1)


class StimulusUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    schema_id: Literal["threemind.stimulus-unit/1"] = VERSION
    kind: Literal["element", "group"]
    time_us: str
    elements: list[Element] = Field(min_length=1, max_length=786432)
    intensity: float = Field(default=1.0, ge=0, le=100)
    source: str = Field(min_length=1, max_length=128)
    capture_time_us: str | None = None
    frame_id: str = Field(default="", max_length=128)
    mapping_version: str = Field(min_length=1, max_length=128)
    grouping_basis: str = Field(default="", max_length=500)
    coordinate_frame: str = Field(default="", max_length=128)
    measurements: list[dict] = Field(default_factory=list, max_length=4096)

    @model_validator(mode="after")
    def valid(self):
        timestamp(self.time_us)
        if self.capture_time_us is not None:
            timestamp(self.capture_time_us)
        if self.kind == "element" and len(self.elements) != 1:
            raise ValueError("an element carrier contains exactly one element")
        if self.kind == "group" and not self.grouping_basis.strip():
            raise ValueError("a group requires an explicit joint-observation basis")
        if len({e.channel for e in self.elements}) != len(self.elements):
            raise ValueError("duplicate channel in one joint observation")
        return self

    def frame(self):
        metadata = self.model_dump(mode="json", exclude={"elements", "intensity", "time_us"})
        return {
            "stimulus": Stimulus(
                timestamp(self.time_us), tuple(sorted((e.channel, e.value) for e in self.elements)), self.intensity
            ),
            "labels": {},
            "stimulus_unit": metadata,
        }


def unit_frames(payload):
    if not isinstance(payload, dict) or set(payload) != {"units"} or not isinstance(payload["units"], list):
        raise ValueError("stimulus-units requires a units array")
    if not 1 <= len(payload["units"]) <= 100000:
        raise ValueError("stimulus-units requires 1 to 100000 units")
    previous = -1
    for raw in payload["units"]:
        encoded = json.dumps(raw, allow_nan=False)
        if len(encoded.encode()) > 4 * 1024 * 1024:
            raise ValueError("stimulus unit exceeds 4 MiB")
        unit = StimulusUnit.model_validate_json(encoded)
        frame = unit.frame()
        if frame["stimulus"].time_us < previous:
            raise ValueError("stimulus units must preserve nondecreasing delivery order")
        previous = frame["stimulus"].time_us
        yield frame
