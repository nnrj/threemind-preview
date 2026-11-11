"""Compact descriptive contrasts from complete recorded worlds; no Core access."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.ocean_cli import read_json

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/ocean-communication-20261006'


def stream(folder, limit_s=None, start_us=None):
    origin = None
    with gzip.open(folder / 'communication.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if start_us is not None and row['time_us'] < start_us:
                continue
            if origin is None:
                origin = row['time_us'] if start_us is None else start_us
            if limit_s is not None and row['time_us'] - origin > limit_s * 1e6:
                return
            yield row


def paired(a, b, seconds, start_us=None):
    left = {r['time_us']: r for r in stream(a, seconds, start_us)}
    if not left:
        return {'samples': 0, 'reason': 'no recorded process'}
    # Branch-local births can reuse a number for different descendants. Only
    # identities already present at the shared starting time are paired.
    initial_ids = {m['id'] for m in next(iter(left.values()))['members']}
    change, paths, ears, count, affected, times = [], [], [], 0, set(), []
    for row in stream(b, seconds, start_us):
        prior = left.get(row['time_us'])
        if prior is None:
            continue
        lookup = {m['id']: m for m in prior['members']}
        for m in row['members']:
            if m['id'] not in lookup or m['id'] not in initial_ids:
                continue
            q = lookup[m['id']]
            delta = float(np.linalg.norm(np.subtract(m['action'], q['action'])))
            displacement = (np.subtract(m['position'], q['position']) + .6) % 1.2 - .6
            change.append(delta)
            paths.append(float(np.linalg.norm(displacement)))
            ears.append(abs(m['hearing_activation'] - q['hearing_activation']))
            count += 1
            if delta > 1e-8:
                affected.add(m['id'])
                times.append(row['time_us'])
    return {'samples': count, 'affected_individuals': len(affected),
            'mean_action_difference': float(np.mean(change)) if change else None,
            'max_action_difference': max(change, default=None),
            'mean_path_distance_m': float(np.mean(paths)) if paths else None,
            'mean_hearing_activation_difference': float(np.mean(ears)) if ears else None,
            'first_change_us': min(times, default=None)}


def outcome(folder):
    final = read_json(folder / 'result.json')
    with gzip.open(folder / 'trajectory.jsonl.gz', 'rt', encoding='utf-8') as f:
        initial = json.loads(next(f))
    food = lambda r: sum(m['grains'] for m in r['members'])
    captures = lambda r: sum(m['captured'] for m in r['members'])
    sound = final['communication']
    difference = {k: v - initial['communication'][k] for k, v in sound.items()}
    groups = {}
    for k, group in final['groups'].items():
        old = initial['groups'][k]
        groups[k] = {field: group[field] - old[field] for field in ('food', 'captures', 'births')}
        groups[k]['physical'] = group['physical']
    pending, succeeded, released, carryover = set(), 0, 0, 0
    for event in read_json(folder / 'events.json'):
        kind = event['kind']
        if kind not in ('capture_started', 'capture_released', 'body_consumed_by_coverage'):
            continue
        pair = (event['predator'], event['individual'])
        if kind == 'capture_started':
            pending.add(pair)
        elif pair in pending:
            pending.remove(pair)
            succeeded += int(kind == 'body_consumed_by_coverage')
            released += int(kind == 'capture_released')
        else:
            carryover += 1
    return {'case': folder.name, 'status': final['status'], 'error': final['error'],
            'time_us': final['time_us'], 'observed_us': final['observed_us'],
            'wall_seconds': final['wall_seconds'], 'new_food': food(final) - food(initial),
            'new_captures': captures(final) - captures(initial),
            'new_capture_starts': final['totals']['capture_starts'] - initial['totals']['capture_starts'],
            'new_deaths': sum(not m['physical'] for m in final['members']) - sum(not m['physical'] for m in initial['members']),
            'new_births': final['totals']['births'] - initial['totals']['births'],
            'physical': sum(m['physical'] for m in final['members']),
            'max_generation': max(m['generation'] for m in final['members']),
            'sharing_energy': sum(m['share_received'] for m in final['members']) - sum(m['share_received'] for m in initial['members']),
            'capture_attempt_outcomes': {'started_and_succeeded': succeeded, 'started_and_released': released,
                                         'no_recorded_end_in_window': len(pending), 'carryover_end_events': carryover},
            'energy_balance_error': final['energy_balance_error'], 'groups': groups, 'sound_delta': difference}


def sound_summary(folder):
    """Describe the actual carrier, without inventing words or meanings."""
    count, previous, changes, powers, shares = 0, {}, [], [], []
    receivers, other_fractions, encoded_values, cohort_profiles = set(), [], [], {}
    cohorts = {}
    for row in stream(folder):
        cohorts.update({m['id']: m['cohort'] for m in row['members']})
        for emission in row['emitted']:
            power = np.asarray(emission['power'], dtype=float)
            total = float(power.sum())
            if not total:
                continue
            profile = power / total  # Analysis only; never a substituted Core input.
            identity = emission['individual']
            if identity in previous:
                changes.append(float(np.abs(profile - previous[identity]).sum()) / 2)
            previous[identity] = profile
            count += 1
            powers.append(total)
            shares.append(float(profile.max()))
            cohort = cohorts.get(identity, 'not_present_in_sample')
            aggregate = cohort_profiles.setdefault(cohort, {'sum': np.zeros(len(profile)), 'count': 0})
            aggregate['sum'] += profile
            aggregate['count'] += 1
        for receiver in row['received']:
            receivers.add(receiver['individual'])
            if receiver['mode'] == 'live':
                total = float(np.asarray(receiver['power']).sum())
                if total:
                    other_fractions.append(receiver['other_power'] / total)
            if receiver.get('stimulus'):
                encoded_values.extend(v for _, v in receiver['stimulus']['channels'])
    return {'nonzero_emissions': count, 'senders': len(previous), 'receivers': len(receivers),
            'mean_total_emitted_power': float(np.mean(powers)) if powers else None,
            'mean_largest_band_fraction': float(np.mean(shares)) if shares else None,
            'mean_adjacent_spectral_change': float(np.mean(changes)) if changes else None,
            'median_adjacent_spectral_change': float(np.median(changes)) if changes else None,
            'fraction_unchanged_spectrum': float(np.mean(np.asarray(changes) < 1e-9)) if changes else None,
            'median_other_power_fraction': float(np.median(other_fractions)) if other_fractions else None,
            'mean_encoded_channel': float(np.mean(encoded_values)) if encoded_values else None,
            'fraction_encoded_above_95pct_gain': float(np.mean(np.asarray(encoded_values) > .114)) if encoded_values else None,
            'cohort_mean_spectrum': {k: (v['sum'] / v['count']).tolist() for k, v in cohort_profiles.items()},
            'normalization_scope': 'offline descriptive statistics only; no simulation input/output changed'}


def hearing_structure(snapshot):
    """Read snapshots only. Count newly available auditory paths, never advance."""
    from lab.tools.ocean_communication import load
    from threemind_runtime.media import organ_output
    world = load(snapshot)
    members = []
    for identity, engine in world.engines.items():
        state = engine.capture_state().to_dict()
        receptors = {n['id'] for n in state['nodes'] if n['channel'] in world.hearing_channels(identity)}
        edges = [e for e in state['edges'] if e['source'] in receptors or e['target'] in receptors]
        voices = organ_output(engine.time_us, engine.activations(), world.acoustic,
                              world.projector, image=False)['voices']
        voice_power = sum(v['amplitude'] ** 2 for v in voices)
        auditory_power = sum(v['amplitude'] ** 2 for v in voices if v['node_id'] in receptors)
        members.append({'id': identity, 'physical': world.bodies[identity].physical,
                        'generation': world.bodies[identity].generation,
                        'auditory_nodes': len(receptors), 'auditory_edges': len(edges),
                        'auditory_to_other_edges': sum((e['source'] in receptors) != (e['target'] in receptors) for e in edges),
                        'auditory_edge_weight': sum(e['weight'] for e in edges),
                        'voices_at_checkpoint': len(voices),
                        'auditory_voices_at_checkpoint': sum(v['node_id'] in receptors for v in voices),
                        'auditory_fraction_of_voice_power_at_checkpoint': auditory_power / voice_power if voice_power else None})
    return {'time_us': world.time_us, 'members': members}


def window_outcome(folder, seconds, start_us=None):
    """Equal observation duration, including when a control stops earlier."""
    with gzip.open(folder / 'trajectory.jsonl.gz', 'rt', encoding='utf-8') as f:
        first = json.loads(next(f))
        if start_us is not None:
            for line in f:
                candidate = json.loads(line)
                if candidate['time_us'] == start_us:
                    first = candidate
                    break
            else:
                return {'available': False, 'reason': 'start sample unavailable'}
        finish = first['time_us'] + round(seconds * 1e6)
        end = None
        if first['time_us'] == finish:
            end = first
        for line in f:
            row = json.loads(line)
            if row['time_us'] == finish:
                end = row
                break
            if row['time_us'] > finish:
                break
    if end is None:
        candidate = read_json(folder / 'result.json')
        if candidate['time_us'] != finish:
            return {'available': False, 'requested_seconds': seconds}
        end = candidate
    return {'available': True, 'seconds': seconds,
            'food': sum(m['grains'] for m in end['members']) - sum(m['grains'] for m in first['members']),
            'consumed_individuals': sum(m['captured'] for m in end['members']) - sum(m['captured'] for m in first['members']),
            'births': end['totals']['births'] - first['totals']['births'],
            'physical': sum(m['physical'] for m in end['members'])}


def main():
    destination = HERE / 'results.json'
    previous = read_json(destination) if destination.exists() else {}
    if previous.get('analysis_version') != 4:
        previous = {}
    cases, interruptions = {}, []
    for path in (WORK / 'cases').glob('*/result.json'):
        row = read_json(path)
        if row['status'] not in ('horizon_paused', 'physical_extinction'):
            interruptions.append({'case': path.parent.name, **{k: row[k] for k in ('status', 'error', 'observed_us', 'wall_seconds')}})
            continue
        name = path.parent.name
        if name == 's1-matched-resume':
            name = 's1-matched'
        cases[name] = path.parent
    measured = []
    for name, folder in cases.items():
        row = outcome(folder)
        row.update(case=name, recording=folder.name)
        measured.append(row)
    result = {'analysis_version': 4, 'cases': measured, 'interrupted_cases': interruptions, 'contrasts': [], 'matching': {},
              'interpretation_unit': 'two environment seeds; forks and time samples are not independent replicates'}
    result['equal_duration_outcomes'] = {
        name: {str(seconds): window_outcome(folder, seconds) for seconds in (1, 5, 20)
               if seconds <= read_json(folder / 'result.json')['observed_us'] / 1e6}
        for name, folder in cases.items() if 'development' not in name}
    # Completed stages are immutable. Reuse derived summaries, not repeated
    # whole-world reads after every subsequently completed comparison.
    prior_sound = previous.get('development_sound', {})
    result['development_sound'] = {name: prior_sound[name] if name in prior_sound else sound_summary(folder) for name, folder in cases.items()
                                   if name.endswith('development-01')}
    result['auditory_structure'] = {}
    for source in (0, 1):
        final = cases.get(f's{source}-development-01')
        if final:
            if str(source) in previous.get('auditory_structure', {}):
                result['auditory_structure'][str(source)] = previous['auditory_structure'][str(source)]
                continue
            result['auditory_structure'][str(source)] = {
                'birth': hearing_structure(WORK / f'sources/{source}'),
                'developed': hearing_structure(final / 'final')}
    result['joint_sampling'] = {}
    for source in (0, 1):
        live, muted = cases.get(f's{source}-joint-development'), cases.get(f's{source}-joint-muted')
        if live:
            cached = previous.get('joint_sampling', {}).get(str(source), {})
            entry = {'structure': cached.get('structure') or hearing_structure(live / 'checkpoints/20000000'),
                     'live_20_30': window_outcome(live, 10, 20000000)}
            if muted:
                entry['muted_20_30'] = window_outcome(muted, 10)
                entry['contrasts'] = {str(seconds): paired(live, muted, seconds, 20020000) for seconds in (1, 5)}
            result['joint_sampling'][str(source)] = entry
    combinations = [('live', x) for x in ('muted', 'scrambled', 'target', 'matched', 'rescue')]
    combinations += [('muted', 'muted-target'), ('muted', 'muted-matched'),
                     ('target', 'muted-target'), ('matched', 'muted-matched'), ('early-live', 'early-muted')]
    for source in (0, 1):
        for a, b in combinations:
            keys = [f's{source}-{x}' for x in (a, b)]
            if not all(k in cases for k in keys):
                continue
            for seconds in (1, 5, 20):
                if ('early' in a or b == 'rescue') and seconds > 5:
                    continue
                result['contrasts'].append({'source': source, 'a': a, 'b': b, 'seconds': seconds,
                                            **paired(cases[keys[0]], cases[keys[1]], seconds)})
        target = cases.get(f's{source}-target')
        if target:
            manifest = read_json(target / 'initial/manifest.json')['context']
            receipt = manifest['coverage']['material']['enclosure']['group']['community']['research']['hearing_edge_intervention']['receipt']
            result['matching'][str(source)] = {
                'individuals': len(receipt),
                'target_edges': sum(len(v['target']) for v in receipt.values()),
                'matched_edges': sum(len(v['matched']) for v in receipt.values()),
                'target_weight': sum(v['target_weight'] for v in receipt.values()),
                'matched_weight': sum(v['matched_weight'] for v in receipt.values())}
    result['total_compute_seconds'] = sum(v['wall_seconds'] for v in [*result['cases'], *interruptions])
    # Derived, explicitly replaceable analysis; raw records remain immutable.
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'completed': len(cases), 'compute_seconds': result['total_compute_seconds'],
                      'cases': [{k: c[k] for k in ('case', 'new_food', 'new_captures', 'physical')} for c in result['cases']]}), flush=True)


if __name__ == '__main__':
    main()
