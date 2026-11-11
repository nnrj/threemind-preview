"""Whole historical /2 worlds and explicitly declared reversible copies.

Preparation only: no entry point, birth, autonomous run or implicit stimulation.
The legacy apparatus and Core implementations remain untouched.
"""
import copy,gzip,hashlib,json,os
from dataclasses import asdict
from pathlib import Path
import pilot_m2 as m
from lab.tools.ocean_communication import JointCommunicationOcean
from threemind_runtime.codec import ArtifactCodec

SCHEMA='threemind.m6-historical-whole/1'
KERNEL='threemind.continuous-memory/2'
WORLD='threemind.ocean-communication/2'
ATTRIBUTES=set(('associations intake association_max_us packets next_sound_us sound_totals last_sound '
    'contests _deciding_contests body_material construction_paid cohorts group_controls cross_only '
    'controls research p backend time_us rng mutations bodies engines seeds projections engulf food '
    'food_ids next_food_id next_food_us totals events pending_shape contacts last_actions input_buses '
    'output acoustic projector').split())
BUS_CACHE=('_frames','_channels','_next_valid','_next_time')


def base(context):
    return context['coverage']['material']['enclosure']['group']['community']['world']


def extras(world):
    if set(vars(world))!=ATTRIBUTES:
        raise ValueError('unaccounted world state: '+str(sorted(set(vars(world))^ATTRIBUTES)))
    if world._deciding_contests:raise ValueError('whole save requires a complete physical boundary')
    if tuple(world.output._subscribers)!=('water-acoustics',):raise ValueError('unexpected output consumers')
    return {'backend':world.backend,'projections':[[s,n,list(v)] for (s,n),v in sorted(world.projections.items())],
            'last_actions':{str(i):list(v) for i,v in world.last_actions.items()},
            'last_sound':copy.deepcopy(world.last_sound),'events':copy.deepcopy(world.events),
            'acoustic':asdict(world.acoustic),'projector':asdict(world.projector),
            'input_buses':{str(i):{'cache':{k:getattr(bus,k) for k in BUS_CACHE},
                          'configuration':asdict(bus.config),'policies':asdict(bus.policies)}
                           for i,bus in world.input_buses.items()}}


def canonical(world):
    if world.p.schema_id!=WORLD:raise ValueError('genuine historical common-sample world /2 required')
    # Integer world/body keys must have the same canonical order before and
    # after JSON restoration. This normalization changes no live object.
    return json.loads(m.encoded({'schema':SCHEMA,'context':world.capture(),'extras':extras(world)}))


def binary_original(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())


def save_whole(world,folder):
    """Immutable complete marker last; no world or Core advancement."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    value=canonical(world);root=base(value['context'])
    for i,e in world.engines.items():
        state=e.capture_state()
        if state.to_dict()['definition']['kernel_id']!=KERNEL:raise ValueError('historical kernel identity changed')
        if state.digest!=root['core_hashes'][str(i)]:raise ValueError('state changed while saving')
        binary_original(folder/f'{i}.tmind',ArtifactCodec.encode(state))
    m.original(folder/'world.json.gz',value,compressed=True)
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}
    receipt={'schema':SCHEMA,'time_us':world.time_us,'canonical_sha256':m.digest(value),'files':files,
             'bodies':len(world.bodies),'cores':len(world.engines),'historical_kernel':KERNEL}
    if m.digest(canonical(world))!=receipt['canonical_sha256']:raise ValueError('saving altered whole state')
    m.original(folder/'complete.json',receipt)
    return receipt


def stored_whole(folder):
    """File-only integrity check: decoding images does not construct engines."""
    folder=Path(folder);receipt=m.read(folder/'complete.json')
    if receipt['schema']!=SCHEMA or receipt['historical_kernel']!=KERNEL:raise ValueError('snapshot identity differs')
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}-{'complete.json'}
    if actual!=set(receipt['files']):raise ValueError('snapshot file membership differs')
    for rel,sha in receipt['files'].items():
        p=(folder/rel).resolve()
        if not p.is_relative_to(folder.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
            raise ValueError('snapshot file checksum differs')
    value=json.loads(gzip.decompress((folder/'world.json.gz').read_bytes()));root=base(value['context'])
    if m.digest(value)!=receipt['canonical_sha256'] or root['time_us']!=receipt['time_us']:
        raise ValueError('whole state/time differs')
    if root['protocol']['schema']!=WORLD:raise ValueError('world identity differs')
    if set(receipt['files'])!={'world.json.gz',*(f'{i}.tmind' for i in root['core_hashes'])}:
        raise ValueError('missing or surplus individual')
    for i,sha in root['core_hashes'].items():
        image=ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes())
        if image.digest!=sha or image.to_dict()['definition']['kernel_id']!=KERNEL:
            raise ValueError('whole individual checksum/identity differs')
    return value,receipt


def restore_whole(folder):
    """Restore complete current state; callers must register causal restorations."""
    folder=Path(folder);value,receipt=stored_whole(folder);context=value['context'];root=base(context)
    images={int(i):ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes()) for i in root['core_hashes']}
    world=JointCommunicationOcean(root['protocol'],state=context,images=images,backend=value['extras']['backend'])
    x=value['extras'];world.projections={(s,n):tuple(v) for s,n,v in x['projections']}
    world.last_actions={int(i):list(v) for i,v in x['last_actions'].items()}
    world.last_sound=copy.deepcopy(x['last_sound']);world.events=copy.deepcopy(x['events'])
    if asdict(world.acoustic)!=x['acoustic'] or asdict(world.projector)!=x['projector']:
        raise ValueError('peripheral configuration differs')
    if set(map(int,x['input_buses']))!=set(world.input_buses):raise ValueError('input bus identities differ')
    for i,body in x['input_buses'].items():
        bus=world.input_buses[int(i)]
        if asdict(bus.config)!=body['configuration'] or asdict(bus.policies)!=body['policies']:
            raise ValueError('input bus configuration differs')
        if set(body['cache'])!=set(BUS_CACHE):raise ValueError('incomplete bus cache')
        for key,v in body['cache'].items():setattr(bus,key,v)
    if m.digest(canonical(world))!=receipt['canonical_sha256']:raise ValueError('whole restoration is not exact')
    return world


def load_historical_parent(folder,expected_files):
    """Exact archived parent with genuine saved identities, no simulated step."""
    folder=Path(folder)
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if actual!=set(expected_files):raise ValueError('historical parent membership differs')
    for rel,sha in expected_files.items():
        p=(folder/rel).resolve()
        if not p.is_relative_to(folder.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
            raise ValueError('historical original differs')
    context=m.read(folder/'manifest.json')['context'];root=base(context)
    if root['protocol']['schema']!=WORLD or root['time_us']!=20_000_000:
        raise ValueError('only the registered historical /2 twenty-second parent is allowed')
    images={}
    for i,sha in root['core_hashes'].items():
        image=ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes())
        if image.digest!=sha or image.to_dict()['definition']['kernel_id']!=KERNEL:
            raise ValueError('historical individual checksum/identity differs')
        images[int(i)]=image
    world=JointCommunicationOcean(root['protocol'],state=context,images=images,backend='native')
    if canonical(world)['context']!=context:raise ValueError('historical world restoration differs')
    return world


def check_native_intervention(before,after,edges):
    """/2 counts two native calls; anything beyond sequence/mask is rejected."""
    if before['definition']['kernel_id']!=KERNEL or before['silenced_nodes'] or before['silenced_edges']:
        raise ValueError('unmasked historical /2 reference required')
    expected=copy.deepcopy(before);expected['sequence']+=2
    expected['silenced_edges']=sorted([list(k) for k in edges])
    if after!=expected:raise ValueError('native intervention changed undeclared state')


def intervene_copy(world,selection,mode,operation):
    """Declared full-world causal copies only; no changes to archived parents."""
    if world.time_us!=20_000_000 or mode not in ('live','muted') or operation not in ('sham','target','matched','restored'):
        raise ValueError('only the preregistered 20-second factorial is supported')
    before=canonical(world);eligible=sorted(r['body'] for r in selection['rows'] if r['valid'])
    if len(eligible)<8:raise ValueError('insufficient frozen eligible bodies')
    if world.p.hearing_mode!='live':raise ValueError('historical parent must be the live-sound reference')
    protocol=world.p.model_dump(by_alias=True);protocol['hearing_mode']=mode
    world.p=world.protocol_model.model_validate(protocol)
    operations=[]
    for row in selection['rows']:
        if not row['valid']:continue
        i=row['body'];engine=world.engines[i];state=engine.capture_state()
        if state.digest!=row['state_sha256']:raise ValueError('selection no longer matches parent')
        pairs=row['pairs'];key='matched' if operation=='matched' else 'target'
        selected=[p[key]['key'] for p in pairs] if operation!='sham' else []
        if operation!='sham' and (len(selected)!=16 or len({tuple(e) for e in selected})!=16):
            raise ValueError('exactly sixteen unique frozen edges required')
        engine.intervene(edges=selected,action='silence')
        engine.intervene(edges=selected if operation=='restored' else [],action='unsilence')
        after=engine.capture_state();mask=[] if operation in ('sham','restored') else selected
        check_native_intervention(state.to_dict(),after.to_dict(),mask)
        operations.append({'body':i,'operation':operation,'edges':selected,'before_sha256':state.digest,
                           'after_sha256':after.digest,'two_native_calls':True,'time_us':engine.time_us})
    after=canonical(world);expected=copy.deepcopy(before)
    base(expected['context'])['protocol']['hearing_mode']=mode
    for operation_row in operations:
        base(expected['context'])['core_hashes'][str(operation_row['body'])]=operation_row['after_sha256']
    if after!=expected:raise ValueError('intervention changed undeclared whole-world state')
    return {'mode':mode,'operation':operation,'eligible':eligible,'operations':operations,
            'before_sha256':m.digest(before),'after_sha256':m.digest(after),
            'world_time_us':world.time_us,'only_declared_mask_hearing_mode_and_native_sequence':True}


def physical_step(world,*,extra_observation=False):
    """One explicit original world step, retaining actually applied actions."""
    start=world.time_us
    if extra_observation:
        before=m.digest(canonical(world));world.metrics()
        for e in world.engines.values():e.activations()
        if m.digest(canonical(world))!=before:raise ValueError('observation altered state')
    observed=[]
    world.step(lambda row:observed.append(copy.deepcopy(row)))
    if len(observed)!=1 or observed[0]['time_us']!=start+world.p.period_us or world.time_us!=start+world.p.period_us:
        raise ValueError('unexpected time advancement or event order')
    return {'action_time_us':start,'time_us':world.time_us,
            'actions':{str(i):list(v) for i,v in world.last_actions.items()},'native':observed[0]}
