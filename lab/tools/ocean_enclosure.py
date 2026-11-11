"""Versioned soft-envelope apparatus, retaining full habitat and unchanged Core.

An enclosing capsule can admit a geometrically smaller capsule through its soft
boundary. Partial overlap never consumes a body. Shell delay/cost and continuous
complete containment remain necessary. This is not a soft-tissue/fluid solver.
"""
from pathlib import Path

from pydantic import Field, model_validator

from lab.tools.ocean_contact import capsule, point_segment
from lab.tools.ocean_groups import GroupOcean, GroupProtocol, SCHEMA as GROUP_STATE
from lab.tools.ocean_cli import read_json
from threemind_runtime.codec import ArtifactCodec

SCHEMA = 'threemind.ocean-enclosure-state/1'


class EnclosureProtocol(GroupProtocol):
    schema_id: str = Field(default='threemind.ocean-enclosure/1', alias='schema')
    capture_enabled: bool = False

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id != 'threemind.ocean-enclosure/1' or self.capture_enabled:
            raise ValueError('enclosure-only protocol required; contact capture is forbidden')
        values = self.model_dump(by_alias=True)
        values['schema'] = 'threemind.ocean-groups/1'
        GroupProtocol.model_validate(values)
        return self


def can_contain_at_common_center(a, b):
    """Geometric fit at the current orientations, without moving either body."""
    aa, ab, ar = capsule(a, origin=[0., 0.])
    ba, bb, br = capsule(b, origin=[0., 0.])
    return (a.radius > b.radius and ar >= br and
            max(float(point_segment(ba, aa, ab)), float(point_segment(bb, aa, ab))) + br <= ar)


class EnclosureOcean(GroupOcean):
    protocol_model = EnclosureProtocol

    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        if state is not None:
            if state.get('schema') != SCHEMA:
                raise ValueError('explicit enclosure state required')
            state = state['group']
        super().__init__(protocol, state=state, images=images, **kwargs)

    def _separate_overlap(self, a, b, gap, normal):
        # Only the membrane's admissibility changes; no pull, steering, food cue,
        # neural reward, or consumption on touch is added. Incompatible shapes
        # still collide. Protected relatives cannot enter one another.
        permitted = self.p.predation and any(
            can_contain_at_common_center(hunter, prey) and
            not self._protected_pair(hunter.id, prey.id, self.time_us)
            for hunter, prey in ((a, b), (b, a)))
        if not permitted:
            super()._separate_overlap(a, b, gap, normal)

    def capture(self):
        return {'schema': SCHEMA, 'group': super().capture()}


def load(folder):
    folder = Path(folder)
    state = read_json(folder / 'manifest.json')['context']
    if state.get('schema') != SCHEMA or state['group']['schema'] != GROUP_STATE:
        raise ValueError('enclosure snapshot required')
    base = state['group']['community']['world']
    images = {int(i): ArtifactCodec.decode((folder / f'{i}.tmind').read_bytes())
              for i in base['core_hashes']}
    return EnclosureOcean(base['protocol'], state=state, images=images)
