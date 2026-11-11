"""Save/reuse complete ocean species candidates without altering Core dynamics.

python -m lab.tools.ocean_species save SNAPSHOT ID OUTPUT --name NAME --evidence JSON
python -m lab.tools.ocean_species import BUNDLE --project UUID
python -m lab.tools.ocean_species list --project UUID
python -m lab.tools.ocean_species export ASSET_ID OUTPUT --project UUID
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from lab.tools.ocean import zero_energy_birth
from lab.tools.ocean_evolution import TRAITS
from lab.tools.ocean_cli import read_json
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_lab.species_library import SCHEMA, inspect_bundle, pack

BODY_TRAITS = (*TRAITS, 'elongation', 'grip')


def save_live_candidate(world, identity, output, *, name, evidence, source,
                        description='Saved immediately after a natural complete-enclosure event.'):
    """Read-only event snapshot; no advance, supply or observer feedback."""
    b=asdict(world.bodies[identity]);image=world.engines[identity].capture_state()
    if hasattr(world, 'body_material'):
        b['body_material_energy'] = world.body_material[identity]
        b['construction_paid'] = world.construction_paid[identity]
    ancestry=[];cursor=world.bodies[identity]
    while cursor is not None and len(ancestry)<100:
        ancestry.append({k:getattr(cursor,k) for k in ('id','parent','generation','radius','elongation','shell')})
        cursor=world.bodies.get(cursor.parent)
    origins=world.research.get('species_founder_batches',[world.research.get('species_founders',{})])
    for origin in origins:
        if ancestry and ancestry[-1]['id'] in origin.get('ids',[]):
            source=source|{'inherited_candidate':origin}
            break
    m=dict(schema=SCHEMA,name=name,description=description,
        kernel_id=image.to_dict()['dynamics'],state_hash=image.digest,
        adapter='ocean-contact-senses-and-motor/3',mapping_seed=world.seeds[identity],body=b,
        traits={k:b[k] for k in BODY_TRAITS},environment_protocol=world.p.model_dump(by_alias=True),
        source=source|{'individual':identity,'world_time_us':world.time_us},evidence=evidence,
        qualification='candidate',lineage=ancestry)
    raw=pack(m,image);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(raw)
    return m


def save_candidate(snapshot, identity, output, *, name, evidence, description=''):
    snapshot, output = Path(snapshot), Path(output)
    c = read_json(snapshot / 'manifest.json')['context']
    if c.get('schema') in ('threemind.ocean-communication-state/1', 'threemind.ocean-communication-state/2'):
        c = c['coverage']
    if c.get('schema') in ('threemind.ocean-association-state/1','threemind.ocean-enclosure-state/3'):
        c = c['material']
    material = c if c.get('schema') == 'threemind.ocean-enclosure-state/2' else None
    if material is not None:
        c = c['enclosure']
    if c.get('schema') != 'threemind.ocean-enclosure-state/1':
        raise ValueError('explicit enclosure snapshot required')
    w = c['group']['community']['world']
    bodies = {b['id']: b for b in w['bodies']}
    b = bodies[identity]
    if material is not None:
        b = b | {'body_material_energy': material['body_material'][str(identity)],
                 'construction_paid': material['construction_paid'][str(identity)]}
    image = ArtifactCodec.decode((snapshot / f'{identity}.tmind').read_bytes())
    ancestry, cursor = [], b
    while cursor is not None and len(ancestry) < 100:
        ancestry.append({k: cursor[k] for k in ('id', 'parent', 'generation', 'radius', 'elongation', 'shell')})
        cursor = bodies.get(cursor['parent'])
    manifest = dict(schema=SCHEMA, name=name, description=description,
        kernel_id=image.to_dict()['dynamics'], state_hash=image.digest,
        adapter='ocean-contact-senses-and-motor/3', mapping_seed=w['seeds'][str(identity)],
        body=b, traits={k:b[k] for k in BODY_TRAITS}, environment_protocol=w['protocol'],
        source={'snapshot':str(snapshot.resolve()), 'individual':identity, 'world_time_us':w['time_us']},
        evidence=evidence, qualification='candidate', lineage=ancestry)
    raw = pack(manifest, image)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f: f.write(raw)
    return manifest


def seed_founders(world, bundle: bytes, identities):
    """Explicit researcher replication into a NEW full habitat, with ordinary endowments.

    Keep original founder positions/neighbours/food. Reset age/counters/activity,
    retain body traits, mapping, structural memory and its kernel identity.
    This is not a natural birth or evidence of environmental selection.
    """
    m, image = inspect_bundle(bundle)
    identities=list(identities)
    origins=world.research.get('species_founder_batches',
        [world.research['species_founders']] if 'species_founders' in world.research else [])
    assigned={i for origin in origins for i in origin['ids']}
    if (not identities or len(set(identities))!=len(identities)
        or any(i not in world.bodies or i in assigned for i in identities)):
        raise ValueError('distinct, existing, previously unassigned founders required')
    if world.time_us or world.p.schema_id not in ('threemind.ocean-enclosure/1', 'threemind.ocean-enclosure/2',
                                                'threemind.ocean-association/1','threemind.ocean-enclosure/3',
                                                'threemind.ocean-communication/1','threemind.ocean-communication/2'):
        raise ValueError('only a new enclosure habitat may receive candidate founders')
    source = m['environment_protocol']
    for key in ('core_capacity', 'projection_gain', 'environment_sense_gain', 'core_overrides'):
        if source[key] != getattr(world.p, key):
            raise ValueError(f'incompatible candidate habitat: {key}')
    if m['adapter'] != 'ocean-contact-senses-and-motor/3':
        raise ValueError('unsupported body adapter')
    import math
    for k in BODY_TRAITS:
        v=m['traits'][k]
        if not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('finite body traits required')
        if k in ('radius','thrust','sensor_range') and v<=0:raise ValueError('positive body dimensions required')
        if k in ('shell','reflectance','grip') and not 0<=v<=1:raise ValueError('body fraction outside [0,1]')
    if not 0<=m['traits']['elongation']<=2 or m['traits']['radius']*6>=world.p.side_m:
        raise ValueError('body incompatible with habitat scale')
    if m['mapping_seed']!=image.to_dict()['config']['seed']:
        raise ValueError('mapping seed must match the archived brain')
    if hasattr(world, 'validate_founder_material'):
        world.validate_founder_material(identities, m['traits'])
    for i in identities:
        b = world.bodies[i]
        for k in BODY_TRAITS: setattr(b, k, m['traits'][k])
        engine = create_engine(state=zero_energy_birth(image), backend=world.backend)
        engine.supply_energy(world.p.initial_energy, time_us=0, source='species-founder-endowment/1')
        engine.advance_to(0)
        world.engines[i], world.seeds[i] = engine, m['mapping_seed']
        if hasattr(world, 'input_buses'):
            # The next physical sample must bind the bus to the installed brain,
            # not the discarded blank founder engine.
            world.input_buses.pop(i, None)
    if hasattr(world, 'replace_founder_material'):
        world.replace_founder_material(identities)
    world.projections.clear()
    origin = {'ids':list(identities), 'source':m['source'],
        'source_state_hash':m['state_hash'], 'library_generation':m['body']['generation'],
        'rule':'research replication; birth/1 structural inheritance; activity reset; equal founder energy'}
    world.research.setdefault('species_founders',origin)
    world.research['species_founder_batches'] = [*origins,origin]
    return m


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('save');s.add_argument('snapshot',type=Path);s.add_argument('individual',type=int)
    s.add_argument('output',type=Path);s.add_argument('--name',required=True);s.add_argument('--evidence',type=Path,required=True)
    s=sub.add_parser('import');s.add_argument('bundle',type=Path);s.add_argument('--project',required=True)
    s=sub.add_parser('list');s.add_argument('--project',required=True)
    s=sub.add_parser('export');s.add_argument('identity');s.add_argument('output',type=Path);s.add_argument('--project',required=True)
    a=p.parse_args()
    if a.command=='save':
        value=save_candidate(a.snapshot,a.individual,a.output,name=a.name,evidence=read_json(a.evidence))
        print(json.dumps(value,ensure_ascii=False));return
    from threemind_lab.config import Settings
    from threemind_lab.database import Database,LOCAL_USER
    from threemind_lab import species_library as lib
    from uuid import UUID
    db=Database(Settings.from_env().database_url)
    try:
        project=UUID(a.project)
        if a.command=='import':value=lib.put(db,project,LOCAL_USER,a.bundle.read_bytes())
        elif a.command=='list':value=lib.listing(db,project)
        else:
            raw=lib.get(db,project,UUID(a.identity),raw=True)
            with a.output.open('xb') as f:f.write(raw)
            value={'output':str(a.output),'bytes':len(raw)}
        print(json.dumps(value,ensure_ascii=False,default=str))
    finally:db.close()


if __name__=='__main__':main()
