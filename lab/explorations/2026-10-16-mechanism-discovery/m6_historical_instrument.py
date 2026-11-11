"""Four-path N0 equality calibration on copies of both historical parents.

Called only by an explicitly guarded one-shot host. No scientific outcomes
or edge selections are adapted to this calibration.
"""
import os
import time
from pathlib import Path
import pilot_m2 as m
import m6_historical_state as state
import m6_historical_evidence as ev
import m6_historical_rig as rig

ROUTES = ('plain', 'observed', 'paused', 'restored')
MID_US = 20_100_000
END_US = 20_200_000


def tasks():
    return [item for world in range(2) for item in (
        {'world': world, 'route': 'parent', 'id': f'n0-w{world}-parent'},
        *({'world': world, 'route': route, 'id': f'n0-w{world}-{route}'} for route in ROUTES))]


def route(work, task, selection, guard, record):
    work = Path(work)
    if task not in tasks() or task['route'] not in ROUTES or task['world'] != selection['world']:
        raise ValueError('unregistered instrument route')
    if rig.stopped(work, guard):
        raise rig.BoundaryPause('stop before N0 path')
    name, index = task['route'], task['world']
    folder = work / 'apparatus' / f'w{index}' / name
    if folder.exists() or (work / 'in-flight.json').exists():
        raise RuntimeError('N0 path previously attempted or incomplete')
    marker = work / 'in-flight.json'
    m.original(marker, {'label': task['id'], 'operation': 'instrument-initialization',
                        'pid': os.getpid(), 'epoch': time.time(), 'scientific_N': 0})
    if name == 'paused':
        parent = work / 'apparatus' / f'w{index}' / 'plain' / 'states' / str(MID_US)
    else:
        parent = work / 'parents' / f'w{index}' / 'states' / str(ev.START_US)
    world = state.restore_whole(parent)
    before = m.digest(state.canonical(world))
    if name != 'paused':
        operation = state.intervene_copy(world, selection, 'live', 'restored' if name == 'restored' else 'sham')
        m.original(folder / 'intervention.json', operation)
    initial = rig.commit_boundary(work, folder, world, task['id'], [], parent_sha256=before, record=record)
    if name == 'paused' and initial['canonical_sha256'] != m.read(parent / 'complete.json')['canonical_sha256']:
        raise ValueError('full N0 resumption is not exact')
    marker.unlink()
    current = initial
    for endpoint in ((END_US,) if name == 'paused' else (MID_US, END_US)):
        current = rig.segment(work, folder, world, endpoint, task['id'], current, guard, record,
                              extra_observation=name == 'observed')
    result = {'task': task, 'initial': initial, 'final': current, 'scientific_N': 0,
              'new_independent_origins': 0, 'simulation_us': END_US - initial['time_us']}
    m.original(folder / 'result.json', result)
    return result


def verify(work):
    """File-only cross-path checks. Every raw frame and whole file is read."""
    work = Path(work)
    worlds = []
    for index in range(2):
        routes = {}
        for name in ROUTES:
            folder = work / 'apparatus' / f'w{index}' / name
            result = m.read(folder / 'result.json')
            if result['task'] != {'world': index, 'route': name, 'id': f'n0-w{index}-{name}'}:
                raise ValueError('instrument identity differs')
            start = MID_US if name == 'paused' else ev.START_US
            initial, final = result['initial'], result['final']
            if initial['time_us'] != start or final['time_us'] != END_US:
                raise ValueError('instrument time differs')
            reference = (work / 'apparatus' / f'w{index}' / 'plain' / 'states' / str(MID_US)
                         if name == 'paused' else work / 'parents' / f'w{index}' / 'states' / str(ev.START_US))
            parent_sha = m.read(reference / 'complete.json')['canonical_sha256']
            for when in ((MID_US, END_US) if name == 'paused' else (ev.START_US, MID_US, END_US)):
                _, receipt = state.stored_whole(folder / 'states' / str(when))
                boundary = m.read(folder / 'boundaries' / f'{when}.json')
                if boundary['time_us'] != when or boundary['canonical_sha256'] != receipt['canonical_sha256']:
                    raise ValueError('instrument whole state differs')
                if ev.inside(work, boundary['path']) != (folder / 'states' / str(when)).resolve():
                    raise ValueError('instrument boundary path differs')
                if when == start and boundary != initial or when == END_US and boundary != final:
                    raise ValueError('instrument result boundary differs')
                if boundary['parent_sha256'] != parent_sha:
                    raise ValueError('instrument complete-current lineage differs')
                parent_sha = boundary['canonical_sha256']
            chain = ev.verify_chain(folder, final['segments'], start, END_US)
            routes[name] = {'initial_sha256': initial['canonical_sha256'], 'final_sha256': final['canonical_sha256'],
                            'trajectory_sha256': chain['raw_sha256'], 'frames': chain['frames']}
        plain = work / 'apparatus' / f'w{index}' / 'plain'
        midpoint = m.read(plain / 'states' / str(MID_US) / 'complete.json')['canonical_sha256']
        last_segment = m.read(plain / 'result.json')['final']['segments'][-1]
        passed = (len({routes[name]['initial_sha256'] for name in ('plain', 'observed', 'restored')}) == 1
                  and len({route['final_sha256'] for route in routes.values()}) == 1
                  and len({routes[name]['trajectory_sha256'] for name in ('plain', 'observed', 'restored')}) == 1
                  and routes['paused']['initial_sha256'] == midpoint
                  and routes['paused']['trajectory_sha256'] == last_segment['raw_sha256']
                  and all(routes[name]['frames'] == (5 if name == 'paused' else 10) for name in ROUTES))
        worlds.append({'world': index, 'passed': passed, 'routes': routes})
    return {'schema': 'threemind.m6-historical-instrument/1', 'worlds': worlds,
            'passed': all(world['passed'] for world in worlds), 'scientific_N': 0,
            'new_independent_origins': 0, 'read_only_verification': True,
            'expectation': 'both worlds: observation, full process resumption and declared mask restoration preserve exact full states and raw trajectories'}
