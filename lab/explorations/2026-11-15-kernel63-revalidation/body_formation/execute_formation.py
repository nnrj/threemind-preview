"""E21C replay apparatus. Only explicit advance operations move simulated time."""
from dataclasses import replace
import copy
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import materials_formation as materials
sys.path.insert(0, str(HERE.parent/'order_recall'))
import compact_run as storage
base = storage.base
assert Path(base.__file__).resolve() == HERE.parent/'order_recall/study.py'
from threemind_runtime.adapters import channel_id
NS = UUID('43ee35e1-0ced-5718-bad9-167f772b2158')


def identities(seed):
    # Original E18/E21 anonymous encoding, checked against the saved target IDs.
    mask = channel_id(seed, 'world-port-v1:physical-world-v1', 0)
    return {**{name: ((4000 << 20) | i) ^ mask for i, name in enumerate(('A', 'B', 'C', 'X', 'Y', 'keep'))},
            'position_positive': (2 << 20) ^ mask, 'position_negative': ((2 << 20) | 1) ^ mask}


def differences(a, b, prefix=''):
    if isinstance(a, dict) and isinstance(b, dict):
        return [row for key in sorted(a.keys() | b.keys())
                for row in differences(a.get(key), b.get(key), f'{prefix}.{key}'.strip('.'))]
    return [] if a == b else [{'path': prefix, 'before': a, 'after': b}]


def inputs(parent, stage, root=materials.OLD, calibration_seed=None, prequeue_blank=False):
    rows = materials.frames(parent, stage, root)
    if calibration_seed is not None:
        before, after = identities(parent['seed']), identities(calibration_seed)
        mask = before['A'] ^ after['A']
        rows = copy.deepcopy(rows)
        for row in rows:
            row['stimulus']['channels'] = [[channel ^ mask, amplitude] for channel, amplitude in row['stimulus']['channels']]
    if prequeue_blank:
        assert stage['kind'] == 'probe' and not stage['physical']
        rows = copy.deepcopy(rows)
        for row in rows: row['enqueue_us'] = stage['begin_us']
    return rows


def execute(parent, stage, folder, initial=None, observer=None, root=materials.OLD,
            calibration_seed=None, mode='observed', prequeue_blank=False, no_reconfigure=False):
    seed = parent['seed'] if calibration_seed is None else calibration_seed
    config = {'seed': seed, 'stp_facilitation_tau_s': 0.,
              'depletion_enabled': parent['teaching_depletion'],
              'context_enabled': parent['teaching_competition']}
    make = lambda state=None: base.resolve_kernel(materials.KERNEL).create(None if state else config, state, backend='native')
    e = make(initial); born = e.capture_state()
    assert e.time_us == stage['begin_us'] and (initial is None or initial.digest == born.digest)
    folder.mkdir(parents=True, exist_ok=False)
    storage.save(folder/'initial.tmind', born)
    snapshots = {}
    if stage['kind'] == 'probe':
        projected_before = base.observe(e)['nodes']
        patch = {'depletion_enabled': stage['test_depletion'], 'context_enabled': stage['test_competition']}
        if no_reconfigure:
            assert all(getattr(e.config, k) == v for k, v in patch.items())
        else:
            e.reconfigure(replace(e.config, **patch))
        after = e.capture_state()
        projected_after = base.observe(e)['nodes']
        assert e.time_us == stage['begin_us']
        storage.save(folder/'intervened.tmind', after)
        base.s.base.original(folder/'intervention.json', {
            'method': 'none' if no_reconfigure else 'public same-time reconfigure',
            'patch': patch, 'before_sha256': born.digest, 'after_sha256': after.digest,
            'advanced_us': 0, 'changes': differences(born.to_dict(), after.to_dict()),
            'projected_before': projected_before, 'projected_after': projected_after})
    deliveries, receipts, events, points = [], [], [], []
    def sink(event, entry):
        if entry: deliveries.append(entry)
    session = base.ReadoutSession(e, record=events.append, config=base.READERS,
                                  state=observer, event_sink=sink)
    base.s.base.original(folder/'initial-observer.json', session.capture())
    rows = inputs(parent, stage, root, calibration_seed, prequeue_blank)
    index, restored, started = 0, False, time.monotonic()
    def guard():
        if time.monotonic()-started > 300: raise RuntimeError('stage budget exceeded; preserve in-flight')
    def queue_due():
        nonlocal index
        while index < len(rows) and rows[index]['enqueue_us'] == e.time_us:
            row = rows[index]
            receipt = session.schedule([{'stimulus': base.Stimulus.from_dict(row['stimulus'])}],
                source=row['source'], adapter_id='registered-E21C-replay', at=0,
                envelope_id=uuid5(NS, parent['key']+'/'+stage['name']+f'/{index}'))[0]
            receipts.append({'enqueue_us': e.time_us, 'receipt': receipt})
            index += 1
    queue_due()
    observing = stage['kind'] == 'probe'
    if observing and mode != 'plain': points.append(base.observe(e))
    while e.time_us < stage['end_us']:
        step = 100000 if mode == 'sparse' or not observing else 20000
        target = min(stage['end_us'], ((e.time_us//step)+1)*step,
                     rows[index]['enqueue_us'] if index < len(rows) else stage['end_us'])
        assert target > e.time_us
        session.advance_to(target, guard=guard)
        assert e.life != 'dead', 'unexpected incomplete state'
        if observing and mode != 'plain' and (e.time_us-stage['begin_us']) % step == 0:
            points.append(base.observe(e))
        if stage['kind'] == 'train' and e.time_us == 19200000:
            teaching = e.capture_state(); storage.save(folder/'before-wait.tmind', teaching)
            snapshots['before-wait'] = teaching.digest
        queue_due()
        if observing and mode in ('restored', 'paused') and not restored and e.time_us >= stage['begin_us']+1000000:
            state, reader = e.capture_state(), session.capture()
            if mode == 'restored':
                e = make(base.ArtifactCodec.decode(base.ArtifactCodec.encode(state)))
                session = base.ReadoutSession(e, record=events.append, state=reader, event_sink=sink)
            else: time.sleep(.01)
            assert e.capture_state().digest == state.digest
            restored = True
    assert index == len(rows) == len(deliveries) and session.bus.pending_count() == 0
    final = e.capture_state(); storage.save(folder/'final.tmind', final)
    result = {'parent': parent, 'stage': stage, 'kernel': materials.KERNEL, 'seed': seed,
              'initial_sha256': born.digest, 'final_sha256': final.digest,
              'parent_sha256': initial.digest if initial else None, 'status': 'complete', 'life': e.life,
              'inputs': len(rows), 'snapshots': snapshots, 'wall_seconds': time.monotonic()-started,
              'calibration_seed': calibration_seed, 'mode': mode, 'prequeue_blank': prequeue_blank,
              'no_reconfigure': no_reconfigure}
    base.s.base.original(folder/'input.json', {'frames': rows, 'mappings': identities(seed)})
    base.s.base.original(folder/'scheduled.json.gz', receipts, compressed=True)
    base.s.base.original(folder/'delivered.json.gz', deliveries, compressed=True)
    base.s.base.original(folder/'trajectory.json.gz', {'points': points, 'events': events}, compressed=True)
    base.s.base.original(folder/'observer.json', session.capture())
    base.s.base.original(folder/'result.json', result)
    return result, final, session.capture()
