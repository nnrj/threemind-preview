"""Recoverable embodied signalling, outside Core, on the complete ocean.

Existing oscillator mouth -> OutputBus -> finite-range acoustic bands ->
anonymous hearing receptors -> InputBus. No words, source IDs, cohort labels,
food coordinates, rewards or observer classifications enter the signal.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import ClassVar, Literal

import numpy as np
from pydantic import Field, model_validator

from lab.tools.ocean import Stimulus, channel, difference, rotation
from lab.tools.ocean_association import AssociationOcean
from lab.tools.ocean_cli import read_json
from lab.tools.ocean_coverage import CoverageOcean, CoverageProtocol
from threemind_runtime.bus import InputBus, OutputBus
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.media import AcousticConfig, ProjectorConfig, organ_output

SCHEMA = 'threemind.ocean-communication-state/1'


class CommunicationProtocol(CoverageProtocol):
    expected_schema: ClassVar[str] = 'threemind.ocean-communication/1'
    schema_id: str = Field(default='threemind.ocean-communication/1', alias='schema')
    founders: int = 37
    population_limit: int = 67
    sound_interval_us: int = Field(default=100000, ge=20000)
    sound_range_m: float = Field(default=.20, gt=0, allow_inf_nan=False)
    sound_reference_m: float = Field(default=.04, gt=0, allow_inf_nan=False)
    sound_speed_m_s: float = Field(default=1500., gt=0, allow_inf_nan=False)
    sound_bands: int = Field(default=8, ge=2, le=48)
    hearing_gain: float = Field(default=.12, ge=0, le=4, allow_inf_nan=False)
    voice_cost_per_s: float = Field(default=.1, ge=0, allow_inf_nan=False)
    hearing_mode: Literal['live', 'muted', 'scrambled'] = 'live'
    self_hearing: bool = True
    intake_share_fraction: float = Field(default=.25, ge=0, le=1, allow_inf_nan=False)
    association_gap_m: float = Field(default=.001, ge=0, le=.02, allow_inf_nan=False)
    association_dwell_us: int = Field(default=1000000, ge=20000)

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id != self.expected_schema:
            raise ValueError(f'{self.expected_schema} required')
        base = {k: v for k, v in self.model_dump(by_alias=True).items()
                if k == 'schema' or k in CoverageProtocol.model_fields}
        base['schema'] = 'threemind.ocean-enclosure/3'
        CoverageProtocol.model_validate(base)
        if self.sound_interval_us % self.period_us or self.association_dwell_us % self.period_us:
            raise ValueError('sound and association periods must contain complete samples')
        if self.sound_range_m > self.side_m / 2:
            raise ValueError('hearing range must not wrap around the whole habitat')
        return self


class CommunicationOcean(CoverageOcean):
    protocol_model = CommunicationProtocol
    state_schema = SCHEMA

    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        self.associations, self.intake, self.association_max_us = {}, {}, 0
        self.packets, self.next_sound_us = [], 0
        self.sound_totals = dict.fromkeys(('emissions', 'delivered', 'muted', 'voice_energy',
                                          'received_power', 'other_received_power', 'expired'), 0.)
        self.last_sound = {'emitted': [], 'received': []}
        buses = {}
        if state is not None:
            if state.get('schema') != self.state_schema:
                raise ValueError('explicit communication snapshot required')
            self.associations = {(a, b): t for a, b, t in state['associations']}
            self.intake = {int(i): v for i, v in state['intake'].items()}
            self.association_max_us = state['association_max_us']
            self.packets = copy.deepcopy(state['packets'])
            self.next_sound_us = state['next_sound_us']
            self.sound_totals = dict(state['sound_totals'])
            buses = state['input_buses']
            state = state['coverage']
        super().__init__(protocol, state=state, images=images, **kwargs)
        self.input_buses = {i: InputBus(e, buses.get(str(i))) for i, e in self.engines.items()}
        self.output = OutputBus()
        self.output.subscribe('water-acoustics', self._transmit)
        self.acoustic = AcousticConfig(enabled=True, output_interval_us=self.p.sound_interval_us)
        self.projector = ProjectorConfig()

    def _ingest(self, active):
        offset = len(self.events)
        super()._ingest(active)
        for event in self.events[offset:]:
            if event['kind'] == 'nutrient_contact':
                i = event['individual']
                self.intake[i] = self.intake.get(i, 0.) + event['energy']

    def _near_pairs(self, active):
        # Compatibility is a declared body/environment property, not a Core label.
        return {p for p in AssociationOcean._near_pairs(self, active)
                if self.cohorts[p[0]] == self.cohorts[p[1]]}

    _update_associations = AssociationOcean._update_associations
    _share_intake = AssociationOcean._share_intake

    def _predation(self, active):
        self._update_associations(active)
        super()._predation(active)
        self._share_intake()

    def _consume_body_energy(self, hunter, prey):
        value = super()._consume_body_energy(hunter, prey)
        self.intake[hunter.id] = self.intake.get(hunter.id, 0.) + value['transferred']
        return value

    def hearing_channels(self, individual):
        return {channel(self.seeds[individual], f'hearing/1:{ear}:{band}')
                for ear in range(2) for band in range(self.p.sound_bands)}

    def _transmit(self, frame):
        p, i = self.p, frame['individual']
        b = self.bodies[i]
        bands = np.zeros(p.sound_bands)
        for voice in frame['organ']['voices']:
            frequency = math.log(voice['frequency_hz'] / self.acoustic.minimum_frequency)
            span = math.log(self.acoustic.maximum_frequency / self.acoustic.minimum_frequency)
            k = min(p.sound_bands - 1, int(frequency / span * p.sound_bands + 1e-9))
            bands[k] += voice['amplitude'] ** 2
        request = float(bands.sum()) * p.voice_cost_per_s * p.sound_interval_us / 1e6
        paid = min(request, b.storage)
        if request > 0:
            bands *= paid / request
        b.storage -= paid
        self.totals['body_heat'] += paid
        self.sound_totals['voice_energy'] += paid
        self.sound_totals['emissions'] += int(bands.any())
        self.last_sound['emitted'].append({'individual': i, 'time_us': self.time_us,
                                         'power': bands.tolist(), 'paid': paid,
                                         'voices': frame['organ']['voices']})
        if not bands.any():
            return
        for j, receiver in self.bodies.items():
            if not receiver.physical or self.engines[j].life == 'dead' or (i == j and not p.self_hearing):
                continue
            delta = difference(b.position, receiver.position, p.side_m)
            distance = float(np.linalg.norm(delta))
            if distance > p.sound_range_m:
                continue
            ears = []
            for sign in (-1, 1):
                ear_offset = rotation(receiver.angle) @ np.array([0., sign * receiver.radius])
                d = float(np.linalg.norm(delta - ear_offset))
                # Soft near-field boundary and geometric spreading of sound power.
                ears.append((bands / (1 + (d / p.sound_reference_m) ** 2)).tolist())
            delay = max(p.period_us, math.ceil(distance / p.sound_speed_m_s * 1e6 / p.period_us) * p.period_us)
            self.packets.append({'sender': i, 'receiver': j, 'emitted_us': self.time_us,
                                 'arrival_us': self.time_us + delay, 'power': ears})

    def _emit(self):
        if self.time_us < self.next_sound_us:
            return
        if self.time_us != self.next_sound_us:
            raise RuntimeError('sound cadence skipped')
        for i, body in self.bodies.items():
            if body.physical and self.engines[i].life != 'dead':
                output = organ_output(self.time_us, self.engines[i].activations(), self.acoustic,
                                      self.projector, image=False)
                self.output.publish({'individual': i, 'organ': output})
        self.next_sound_us += self.p.sound_interval_us

    def _hearing(self, i, *, enqueue=True):
        due = [q for q in self.packets if q['receiver'] == i and q['arrival_us'] <= self.time_us]
        self.packets = [q for q in self.packets if not (q['receiver'] == i and q['arrival_us'] <= self.time_us)]
        if not due:
            return None
        # Sources mix at the ear. Sender/ancestry/food labels never reach Core.
        shape = (2, self.p.sound_bands)
        own = sum((np.asarray(q['power']) for q in due if q['sender'] == i), np.zeros(shape))
        others = sum((np.asarray(q['power']) for q in due if q['sender'] != i), np.zeros(shape))
        other = float(others.sum())
        if self.p.hearing_mode == 'scrambled':
            # A NEW permutation per arrival, not a fixed, learnable new vocabulary.
            rng = np.random.default_rng(np.random.SeedSequence([self.p.environment_seed, i, self.time_us, 5301]))
            others = others[:, rng.permutation(self.p.sound_bands)]
        if self.p.hearing_mode == 'muted':
            self.sound_totals['muted'] += sum(q['sender'] != i for q in due)
            others *= 0
        power = own + others
        encoded = self.p.hearing_gain * np.tanh(np.sqrt(power))
        row = {'individual': i, 'time_us': self.time_us, 'power': power.tolist(),
               'other_power': other, 'packets': due, 'mode': self.p.hearing_mode}
        if power.any() and self.p.hearing_gain:
            values = tuple(sorted((channel(self.seeds[i], f'hearing/1:{ear}:{band}'), float(encoded[ear, band]))
                                  for ear in range(2) for band in range(self.p.sound_bands) if encoded[ear, band] > 0))
            stimulus = Stimulus(self.time_us - self.bodies[i].birth_us, values)
            if enqueue:
                bus = self.input_buses.setdefault(i, InputBus(self.engines[i]))
                bus.schedule(stimulus, {'source': 'ocean-hearing/1', 'global_time_us': self.time_us,
                                        'sampling': 'simultaneous-ear-band-power', 'budgeted': True})
            row['stimulus'] = stimulus.to_dict()
            self.sound_totals['delivered'] += sum(q['sender'] == i or self.p.hearing_mode != 'muted' for q in due)
            self.sound_totals['received_power'] += float(power.sum())
            self.sound_totals['other_received_power'] += float(others.sum())
        self.last_sound['received'].append(row)
        return row

    def _sensory_sample(self, i, stimulus, bus):
        bus.schedule(stimulus, {'source': 'ocean-body/3', 'global_time_us': self.time_us})
        return self._hearing(i), stimulus

    def _advance_body_input(self, i, b, actions, initial_v):
        e, p = self.engines[i], self.p
        when, offer, item = self.time_us - b.birth_us, 0., None
        bus = self.input_buses.setdefault(i, InputBus(e))
        if b.physical:
            acceleration = rotation(b.angle).T @ ((np.asarray(b.velocity) - initial_v[i]) / (p.period_us / 1e6))
            b.acceleration_x, b.acceleration_y = map(float, acceleration)
            offer = min(b.storage, max(0., p.initial_energy - e.metrics()['energy']['reserve']))
            if offer > 0:
                e.supply_energy(offer, time_us=when, source='nutrient-contact/3')
                b.storage -= offer
                b.supplied += offer
            channels, physical = self.senses(i)
            stimulus = Stimulus(when, channels)
            heard, applied = self._sensory_sample(i, stimulus, bus)
            item = {'individual': i, 'stimulus': applied.to_dict(), 'food': offer,
                    'raw': physical, 'action': actions[i], 'heard': heard}
        e.advance_to(when, observer=bus.observe, inputs_only=True)
        if e.life == 'dead':
            b.physical, b.death_us = False, self.time_us
            self.events.append({'kind': 'consciousness_dead', 'time_us': self.time_us,
                                'individual': i, 'energy': e.metrics()['energy'], 'consumed_by': b.consumed_by})
        return item

    def step(self, record=None):
        self.last_sound = {'emitted': [], 'received': []}
        self._emit()
        def observe(row):
            row['communication'] = self.last_sound
            if record:
                record(row)
        value = super().step(observe)
        retained = [q for q in self.packets if self.bodies[q['receiver']].physical
                    and self.engines[q['receiver']].life != 'dead']
        self.sound_totals['expired'] += len(self.packets) - len(retained)
        self.packets = retained
        return value

    def metrics(self):
        value = super().metrics()
        value['communication'] = dict(self.sound_totals)
        value['association_pairs'] = len(self.associations)
        value['association_max_us'] = self.association_max_us
        return value

    def capture(self):
        return {'schema': self.state_schema, 'coverage': super().capture(),
                'associations': [[a, b, t] for (a, b), t in sorted(self.associations.items())],
                'intake': copy.deepcopy(self.intake), 'association_max_us': self.association_max_us,
                'packets': copy.deepcopy(self.packets), 'next_sound_us': self.next_sound_us,
                'sound_totals': dict(self.sound_totals),
                'input_buses': {str(i): bus.capture() for i, bus in self.input_buses.items()}}


class JointCommunicationProtocol(CommunicationProtocol):
    """Explicit common bodily observation; never silently upgrades /1."""
    expected_schema: ClassVar[str] = 'threemind.ocean-communication/2'
    schema_id: str = Field(default='threemind.ocean-communication/2', alias='schema')


class JointCommunicationOcean(CommunicationOcean):
    protocol_model = JointCommunicationProtocol
    state_schema = 'threemind.ocean-communication-state/2'

    def _sensory_sample(self, i, stimulus, bus):
        heard = self._hearing(i, enqueue=False)
        values = list(stimulus.channels)
        if heard and 'stimulus' in heard:
            values.extend((int(c), float(v)) for c, v in heard['stimulus']['channels'])
        if len({c for c, _ in values}) != len(values):
            raise ValueError('body/ear anonymous channel collision; do not combine unrelated values')
        combined = Stimulus(stimulus.time_us, tuple(sorted(values)), stimulus.intensity)
        bus.schedule(combined, {'source': 'ocean-bodily-observation/2', 'global_time_us': self.time_us,
                                'sampling': 'same-body-same-physical-sample',
                                'components': ['ocean-body/3', 'ocean-hearing/1']})
        if heard:
            heard['delivery_group'] = 'same-body-same-physical-sample'
            heard['combined_stimulus'] = combined.to_dict()
        return heard, combined


def load(folder):
    folder = Path(folder)
    state = read_json(folder / 'manifest.json')['context']
    kind = {SCHEMA: CommunicationOcean, JointCommunicationOcean.state_schema: JointCommunicationOcean}.get(state.get('schema'))
    if kind is None:
        raise ValueError('communication snapshot required')
    base = state['coverage']['material']['enclosure']['group']['community']['world']
    images = {int(i): ArtifactCodec.decode((folder / f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
    return kind(base['protocol'], state=state, images=images)
