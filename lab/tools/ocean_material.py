"""Enclosure /2: digestible body material funded by actual construction payments.

Separate environmental version. Core, motor controls, sensory mapping and the
enclosure/shell criteria are unchanged. Old /1 states cannot silently enter /2.
"""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

from pydantic import Field, model_validator

from lab.tools.ocean_cli import read_json
from lab.tools.ocean_enclosure import EnclosureOcean, EnclosureProtocol
from threemind_runtime.codec import ArtifactCodec

SCHEMA = 'threemind.ocean-enclosure-state/2'


class MaterialProtocol(EnclosureProtocol):
    schema_id: str = Field(default='threemind.ocean-enclosure/2', alias='schema')
    body_material_fraction: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id != 'threemind.ocean-enclosure/2':
            raise ValueError('material environment /2 required')
        values = self.model_dump(by_alias=True)
        values.pop('body_material_fraction')
        values['schema'] = 'threemind.ocean-enclosure/1'
        EnclosureProtocol.model_validate(values)
        return self


class MaterialOcean(EnclosureOcean):
    protocol_model = MaterialProtocol

    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        self.body_material = {}
        self.construction_paid = {}
        if state is not None:
            if state.get('schema') != SCHEMA:
                raise ValueError('explicit material /2 state required; no automatic upgrade')
            self.body_material = {int(k): v for k, v in state['body_material'].items()}
            self.construction_paid = {int(k): v for k, v in state['construction_paid'].items()}
            state = state['enclosure']
            super().__init__(protocol, state=state, images=images, **kwargs)
            for values in (self.body_material, self.construction_paid):
                if set(values) != set(self.bodies) or any(not math.isfinite(v) or v < 0 for v in values.values()):
                    raise ValueError('finite material accounts required for every body')
            if abs(self.metrics()['energy_balance_error']) > 1e-4:
                raise ValueError('material energy ledger does not close')
        else:
            super().__init__(protocol, images=images, **kwargs)
            # Founder bodies are paid from their ordinary body endowment. This
            # avoids adding energy to a larger body just because it was copied.
            self.replace_founder_material(list(self.bodies))

    def construction_cost(self, traits):
        return self.p.construction_energy * (traits['radius'] / self.p.radius_m)**3 * (1 + traits['shell'])

    def validate_founder_material(self, identities, traits=None):
        if self.time_us:
            raise ValueError('founder construction can only be assigned at time zero')
        for i in identities:
            b = self.bodies[i]
            cost = self.construction_cost(traits or {'radius': b.radius, 'shell': b.shell})
            available = b.storage + self.construction_paid.get(i, 0.)
            if cost > available:
                raise ValueError(f'founder {i} body endowment cannot fund construction ({cost:g} > {available:g})')

    def replace_founder_material(self, identities):
        """Explicit time-zero body replacement; refund and reassign the same budget."""
        self.validate_founder_material(identities)
        for i in identities:
            b = self.bodies[i]
            old = self.construction_paid.get(i, 0.)
            cost = self.construction_cost({'radius': b.radius, 'shell': b.shell})
            b.storage += old - cost
            self.totals['body_heat'] += (cost - old) * (1 - self.p.body_material_fraction)
            self.body_material[i] = cost * self.p.body_material_fraction
            self.construction_paid[i] = cost

    def _reproduce(self):
        old = set(self.bodies)
        super()._reproduce()
        for i in self.bodies.keys() - old:
            event = next(e for e in reversed(self.events) if e['kind'] == 'birth' and e['individual'] == i)
            cost = event['construction_cost']
            retained = cost * self.p.body_material_fraction
            # The parent already paid this full cost in EvolutionOcean. Retain
            # part as material instead of counting all of it as dissipated heat.
            self.totals['reproduction_heat'] -= retained
            self.body_material[i] = retained
            self.construction_paid[i] = cost
            event['body_material_energy'] = retained
            event['construction_heat'] = cost - retained

    def _consume_body_energy(self, hunter, prey):
        reserve, material = prey.storage, self.body_material[prey.id]
        potential = (reserve + material) * self.p.predation_efficiency
        received = min(potential, max(0., self.p.storage_capacity - hunter.storage))
        material_received = received * material / (reserve + material) if reserve + material else 0.
        hunter.storage += received
        self.totals['predation_heat'] += reserve + material - received
        prey.storage = 0.
        self.body_material[prey.id] = 0.
        return {'transferred': received, 'prey_reserve': reserve, 'prey_material': material,
                'material_received': material_received, 'reserve_received': received - material_received,
                'digestion_loss': reserve + material - received}

    def metrics(self):
        out = super().metrics()
        out['energy_balance_error'] -= math.fsum(self.body_material.values())
        out['body_material_total'] = math.fsum(self.body_material.values())
        for row in out['members']:
            row['body_material_energy'] = self.body_material[row['id']]
            row['construction_paid'] = self.construction_paid[row['id']]
        return out

    def capture(self):
        return {'schema': SCHEMA, 'enclosure': super().capture(),
                'body_material': copy.deepcopy(self.body_material),
                'construction_paid': copy.deepcopy(self.construction_paid)}


def load(folder):
    folder = Path(folder)
    state = read_json(folder / 'manifest.json')['context']
    if state.get('schema') != SCHEMA:
        raise ValueError('material /2 snapshot required')
    base = state['enclosure']['group']['community']['world']
    images = {int(i): ArtifactCodec.decode((folder / f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
    return MaterialOcean(base['protocol'], state=state, images=images)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('protocol', type=Path); init.add_argument('output', type=Path)
    init.add_argument('--candidate', type=Path); init.add_argument('--candidate-founders', type=int, nargs='+')
    run = commands.add_parser('run')
    run.add_argument('snapshot', type=Path); run.add_argument('output', type=Path)
    run.add_argument('--seconds', type=float, required=True)
    run.add_argument('--wall-seconds', type=int, default=3600)
    args = p.parse_args()
    from lab.tools.ocean_contact_cli import save, run as execute
    if args.command == 'init':
        if bool(args.candidate) != bool(args.candidate_founders):
            p.error('--candidate and --candidate-founders must be supplied together')
        world = MaterialOcean(read_json(args.protocol))
        if args.candidate:
            from lab.tools.ocean_species import seed_founders
            seed_founders(world, args.candidate.read_bytes(), args.candidate_founders)
        world.configure({i: 'all' for i in world.bodies}, {'all': 'core'})
        save(world, args.output)
    else:
        if not math.isfinite(args.seconds) or args.seconds <= 0 or args.wall_seconds <= 0:
            p.error('positive finite simulation and wall durations required')
        execute(load(args.snapshot), args.output, args.seconds, wall_seconds=args.wall_seconds,
                checkpoint_s=min(args.seconds, 150), trajectory_interval_us=100000, activity_interval_us=1000000)


if __name__ == '__main__':
    main()
