"""Declared M6 historical copies with complete physical-boundary commits.

These are callable preparation tools, not a launcher. A guarded, registered
host must hold the existing study lock before any function advances a world.
"""
import os
import time
from pathlib import Path
import pilot_m2 as m
import m6_historical_state as state
import m6_historical_evidence as ev


class BoundaryPause(RuntimeError):
    pass


def stopped(work, guard):
    if not guard.thread.is_alive() and not (work / 'STOP').exists():
        raise RuntimeError('resource guard disappeared without a stop request')
    return (work / 'STOP').exists()


def observed_metrics(world):
    before = m.digest(state.canonical(world))
    metrics = world.metrics()
    if m.digest(state.canonical(world)) != before:
        raise ValueError('metrics changed the complete world')
    return metrics


def commit_boundary(work, folder, world, label, segments, *, parent_sha256, record):
    checkpoint = folder / 'states' / str(world.time_us)
    snapshot = state.save_whole(world, checkpoint)
    metrics = observed_metrics(world)
    boundary = {'label': label, 'time_us': world.time_us,
                'path': checkpoint.relative_to(work).as_posix(),
                'canonical_sha256': snapshot['canonical_sha256'],
                'parent_sha256': parent_sha256, 'segments': segments,
                'metrics': metrics}
    m.original(folder / 'boundaries' / f'{world.time_us}.json', boundary)
    m.atomic_json(work / 'current-boundary.json', boundary)
    record(boundary)
    return boundary


def segment(work, folder, world, end_us, label, prior, guard, record, *, extra_observation=False):
    """A STOP saves the just-completed physical step, never skips an experience."""
    work, folder = Path(work), Path(folder)
    if stopped(work, guard):
        raise BoundaryPause('stop before next physical segment')
    start = world.time_us
    if start != prior['time_us'] or end_us <= start or (end_us - start) % ev.PERIOD_US:
        raise ValueError('segment does not continue the exact current boundary')
    if world.p.period_us != ev.PERIOD_US or m.digest(state.canonical(world)) != prior['canonical_sha256']:
        raise ValueError('current whole-world identity differs')
    marker = work / 'in-flight.json'
    if marker.exists():
        raise RuntimeError('incomplete scientific segment; never retry or roll back')
    m.original(marker, {'label': label, 'start_us': start, 'requested_end_us': end_us,
                        'parent_sha256': prior['canonical_sha256'], 'pid': os.getpid(), 'epoch': time.time()})
    writer = ev.Trajectory(folder / 'trajectories' / f'{start}.jsonl.gz', start)
    try:
        while world.time_us < end_us:
            if stopped(work, guard):
                break
            writer.append(state.physical_step(world, extra_observation=extra_observation))
        receipt = writer.finish()
        # A STOP racing before the first step leaves the same complete parent.
        if receipt['frames']:
            receipt['path'] = writer.path.relative_to(folder).as_posix()
            boundary = commit_boundary(work, folder, world, label, prior['segments'] + [receipt],
                                       parent_sha256=prior['canonical_sha256'], record=record)
        else:
            boundary = prior
            m.original(folder / 'empty-segments' / f'{start}.json', receipt)
        marker.unlink()  # Only after the full current state and raw segment committed.
    except BaseException:
        writer.abort()  # The marker and partial/original evidence remain untouched.
        raise
    if stopped(work, guard) or world.time_us != end_us:
        raise BoundaryPause('complete physical boundary preserved')
    return boundary


def prepare_parent(work, selection, expected_files, *, record):
    """Historical recovery once per world; no simulated advance and no birth."""
    work = Path(work)
    label = f'w{selection["world"]}-parent'
    folder = work / 'parents' / f'w{selection["world"]}'
    if folder.exists():
        raise FileExistsError('historical parent already prepared')
    if (work / 'in-flight.json').exists():
        raise RuntimeError('incomplete prior operation')
    m.original(work / 'in-flight.json', {'label': label, 'operation': 'historical-parent-restoration',
                                        'pid': os.getpid(), 'epoch': time.time()})
    world = state.load_historical_parent(m.ROOT / selection['parent_path'], expected_files)
    boundary = commit_boundary(work, folder, world, label, [], parent_sha256=None, record=record)
    if boundary['time_us'] != ev.START_US:
        raise ValueError('historical time differs')
    (work / 'in-flight.json').unlink()
    return boundary


def run_branch(work, case, selection, guard, record):
    """One named causal world from its intact historical reference, ten seconds."""
    work = Path(work)
    case = ev.checked_case(case)
    if selection['world'] != case['world']:
        raise ValueError('parent selection does not belong to this environment')
    folder = work / 'branches' / case['id']
    if folder.exists() or (work / 'in-flight.json').exists():
        raise RuntimeError('branch previously attempted; inspect, do not restart')
    if stopped(work, guard):
        raise BoundaryPause('stop before declared causal branch')
    parent = work / 'parents' / f'w{case["world"]}' / 'states' / str(ev.START_US)
    m.original(work / 'in-flight.json', {'label': case['id'], 'operation': 'causal-initialization',
                                        'pid': os.getpid(), 'epoch': time.time()})
    world = state.restore_whole(parent)
    before = m.digest(state.canonical(world))
    operation = state.intervene_copy(world, selection, case['mode'], case['operation'])
    m.original(folder / 'intervention.json', operation)
    initial = commit_boundary(work, folder, world, case['id'], [], parent_sha256=before, record=record)
    (work / 'in-flight.json').unlink()
    primary = segment(work, folder, world, ev.START_US + 1_000_000, case['id'], initial, guard, record)
    final = segment(work, folder, world, ev.END_US, case['id'], primary, guard, record)
    chain = ev.verify_chain(folder, final['segments'], ev.START_US, ev.END_US)
    result = {'case': case, 'eligible': operation['eligible'], 'initial': initial, 'primary': primary,
              'final': final, 'trajectory_sha256': chain['raw_sha256'], 'frames': chain['frames'],
              'new_independent_origins': 0, 'historical_parent_time_us': ev.START_US,
              'kernel': state.KERNEL, 'world_protocol': state.WORLD}
    m.original(folder / 'result.json', result)
    return result
