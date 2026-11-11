"""Independent file-only scientific arithmetic; never constructs a world.

The direct Python loops do not call the primary NumPy scoring functions.
Complete snapshot decoding and raw evidence checks precede all conclusions.
"""
import copy
import math
from pathlib import Path
import pilot_m2 as m
import m6_historical_evidence as ev
import m6_historical_state as state
from lab.tools.ocean import channel


def audit_selection(parent_path, selection):
    """Independent saved-time feature/caliper calculation for selected pairs."""
    value, receipt = state.stored_whole(parent_path)
    root = state.base(value['context'])
    bodies = {body['id']: body for body in root['bodies']}
    alive = set()
    for identity in root['core_hashes']:
        image = state.ArtifactCodec.decode((parent_path / f'{identity}.tmind').read_bytes())
        if bodies[int(identity)]['physical'] and image.to_dict()['life'] != 'dead':
            alive.add(int(identity))
    if {row['body'] for row in selection['rows']} != alive:
        raise ValueError('selection omitted or added a historical living body')
    seen = set()
    for row in selection['rows']:
        identity = row['body']
        if identity in seen or identity not in bodies or not bodies[identity]['physical']:
            raise ValueError('selection identity is duplicated or not a live physical body')
        seen.add(identity)
        image = state.ArtifactCodec.decode((parent_path / f'{identity}.tmind').read_bytes())
        source = image.to_dict()
        if image.digest != row['state_sha256'] or source['life'] == 'dead':
            raise ValueError('selection is not bound to this living historical individual')
        if not row['valid']:
            if row['pairs']:
                raise ValueError('excluded body contains an intervention')
            continue
        if len(row['pairs']) != 16:
            raise ValueError('selected matching size differs')
        hearing_channels = {channel(root['seeds'][str(identity)], f'hearing/1:{ear}:{band}')
                            for ear in range(2) for band in range(8)}
        nodes = {node['id']: node for node in source['nodes']}
        hearing = {key for key, node in nodes.items() if node['channel'] in hearing_channels}
        edges = {(edge['source'], edge['target']): edge for edge in source['edges']}
        outgoing = {key: 0 for key in nodes}
        incoming = dict(outgoing)
        for src, dst in edges:
            outgoing[src] += 1
            incoming[dst] += 1
        traces = {(row['source'], row['target']): row['state'] for row in source['operator_state']['fast']}
        config = source['config']
        def features(key):
            edge = edges[key]
            effective = edge['weight']
            if config['fast_enabled']:
                trace = traces.get(key, {'value': 0., 'time_us': edge['birth_us']})
                age = (int(source['time_us']) - int(trace['time_us'])) / 1e6
                if age < 0:
                    raise ValueError('future trace')
                effective = min(1., effective + config['fast_gain'] * trace['value'] * math.exp(-age / config['fast_tau_s']))
            return {'slow_weight': edge['weight'], 'effective_weight': effective,
                    'source_out': outgoing[key[0]], 'source_in': incoming[key[0]],
                    'target_out': outgoing[key[1]], 'target_in': incoming[key[1]],
                    'source_activation': nodes[key[0]]['activation'], 'target_activation': nodes[key[1]]['activation']}
        target_keys, matched_keys = set(), set()
        limits = {'slow_weight': .05, 'effective_weight': .05, 'source_out': 2., 'source_in': 2.,
                  'target_out': 2., 'target_in': 2., 'source_activation': .1, 'target_activation': .1}
        for pair in row['pairs']:
            target, matched = tuple(pair['target']['key']), tuple(pair['matched']['key'])
            if target in target_keys or matched in matched_keys or target not in edges or matched not in edges:
                raise ValueError('duplicate or nonexistent matched edge')
            if ((target[0] in hearing) == (target[1] in hearing)) or set(matched) & hearing:
                raise ValueError('target/control modality does not match the registered contrast')
            target_keys.add(target)
            matched_keys.add(matched)
            x, y = features(target), features(matched)
            for name, limit in limits.items():
                residual = abs(x[name] - y[name])
                if residual > limit or not math.isclose(residual, pair['residual'][name], rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('independently computed matching residual differs')
                if not math.isclose(x[name], pair['target']['features'][name], rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('target feature differs')
                if not math.isclose(y[name], pair['matched']['features'][name], rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('matched feature differs')
    return {'parent_sha256': receipt['canonical_sha256'], 'eligible': sorted(row['body'] for row in selection['rows'] if row['valid'])}


def independent_scores(arms, eligible, restoration):
    expected = {f'{mode}-{op}' for mode in ev.MODES for op in ev.OPERATIONS}
    if set(arms) != expected or set(restoration) != set(ev.MODES):
        raise ValueError('incomplete factorial or restoration checks')
    if sorted(set(eligible)) != list(eligible):
        raise ValueError('fixed unique sorted eligible denominator required')
    times = list(range(20_000_000, 21_000_000, 20_000))
    for rows in arms.values():
        if [row['action_time_us'] for row in rows] != times:
            raise ValueError('independent primary window check failed')
        for row in rows:
            ev.validate_row(row, row['action_time_us'])
    rms = {}
    for operation in ev.OPERATIONS:
        left, right = arms[f'live-{operation}'], arms[f'muted-{operation}']
        squares = []
        for j in range(50):
            for identity in eligible:
                x = left[j]['actions'].get(str(identity), (0., 0., 0.))
                y = right[j]['actions'].get(str(identity), (0., 0., 0.))
                squares.extend((x[k] - y[k]) ** 2 for k in range(3))
        rms[operation] = math.sqrt(math.fsum(squares) / (50 * len(eligible) * 3)) if eligible else 0.
    baseline = rms['sham']
    attenuation = {key: 1 - rms[key] / baseline if baseline > 0 else None
                   for key in ('target', 'matched', 'restored')}
    selectivity = attenuation['target'] - attenuation['matched'] if baseline > 0 else None
    valid = len(eligible) >= 8 and baseline >= .01 and all(restoration.values())
    reached = valid and attenuation['target'] >= .25 and selectivity >= .20
    return {'partner_action_rms': rms, 'attenuation': attenuation, 'selectivity': selectivity,
            'measurement_valid': valid, 'verdict': 'PASS' if reached else 'FAIL' if valid else 'MEASUREMENT_NOT_QUALIFIED'}


def audit_initial(parent, initial, intervention, selection):
    """Read-back whole context changes only at hearing mode and declared Core hashes."""
    before, old_receipt = parent
    after, new_receipt = initial
    if old_receipt['time_us'] != 20_000_000 or new_receipt['time_us'] != 20_000_000:
        raise ValueError('causal initial time differs')
    eligible = sorted(row['body'] for row in selection['rows'] if row['valid'])
    if intervention['eligible'] != eligible or [row['body'] for row in intervention['operations']] != eligible:
        raise ValueError('causal denominator or intervention identities changed')
    if (intervention['before_sha256'], intervention['after_sha256']) != (
            old_receipt['canonical_sha256'], new_receipt['canonical_sha256']):
        raise ValueError('causal initial provenance differs')
    wanted = copy.deepcopy(before)
    state.base(wanted['context'])['protocol']['hearing_mode'] = intervention['mode']
    for row in intervention['operations']:
        key = str(row['body'])
        if row['before_sha256'] != state.base(before['context'])['core_hashes'][key]:
            raise ValueError('wrong intervention reference')
        state.base(wanted['context'])['core_hashes'][key] = row['after_sha256']
    if wanted != after:
        raise ValueError('undeclared whole-world change')


def branch(work, case, selection):
    work = Path(work)
    case = ev.checked_case(case)
    folder = work / 'branches' / case['id']
    result = m.read(folder / 'result.json')
    operation = m.read(folder / 'intervention.json')
    if result['case'] != case or (operation['mode'], operation['operation']) != (case['mode'], case['operation']):
        raise ValueError('branch identity differs')
    parent_path = work / 'parents' / f'w{case["world"]}' / 'states' / '20000000'
    parent = state.stored_whole(parent_path)
    snapshots = []
    for key, when in (('initial', 20_000_000), ('primary', 21_000_000), ('final', 30_000_000)):
        bound = result[key]
        expected = folder / 'states' / str(when)
        if ev.inside(work, bound['path']) != expected.resolve() or bound['time_us'] != when:
            raise ValueError('snapshot path/time does not belong to this branch')
        value, receipt = state.stored_whole(expected)
        if bound['canonical_sha256'] != receipt['canonical_sha256']:
            raise ValueError('boundary whole hash differs')
        if bound != m.read(folder / 'boundaries' / f'{when}.json'):
            raise ValueError('boundary record differs')
        snapshots.append((value, receipt))
    audit_initial(parent, snapshots[0], operation, selection)
    # Reconstruct expected masks and sequence without calling any native intervention.
    selected = {row['body']: row for row in selection['rows'] if row['valid']}
    initial_path = folder / 'states' / '20000000'
    for body in state.base(parent[0]['context'])['core_hashes']:
        old = state.ArtifactCodec.decode((parent_path / f'{body}.tmind').read_bytes()).to_dict()
        new = state.ArtifactCodec.decode((initial_path / f'{body}.tmind').read_bytes()).to_dict()
        expected = copy.deepcopy(old)
        if int(body) in selected:
            source = selected[int(body)]
            expected['sequence'] += 2
            kind = case['operation']
            mask = [pair['matched' if kind == 'matched' else 'target']['key'] for pair in source['pairs']]
            expected['silenced_edges'] = sorted(mask) if kind in ('target', 'matched') else []
        if new != expected:
            raise ValueError('Core changed outside the declared mask and two native sequence counts')
    if result['initial']['segments'] or len(result['primary']['segments']) != 1 or len(result['final']['segments']) != 2:
        raise ValueError('ordinary course/trajectory structure differs')
    if result['final']['segments'][:1] != result['primary']['segments']:
        raise ValueError('final trajectory does not include the committed primary experience')
    for previous, current in ((result['initial'], result['primary']), (result['primary'], result['final'])):
        if current['parent_sha256'] != previous['canonical_sha256']:
            raise ValueError('whole current-state lineage differs')
    if result['initial']['parent_sha256'] != parent[1]['canonical_sha256']:
        raise ValueError('historical reference lineage differs')
    chain = ev.verify_chain(folder, result['final']['segments'], 20_000_000, 30_000_000)
    if (chain['raw_sha256'], chain['frames']) != (result['trajectory_sha256'], result['frames']) or chain['frames'] != 500:
        raise ValueError('full trajectory result differs')
    if result['eligible'] != operation['eligible']:
        raise ValueError('outcome-conditioned denominator')
    return result, chain['primary']


def check(work):
    work = Path(work)
    if any((work / name).exists() for name in ('STOP', 'in-flight.json', 'apparatus-in-flight.json')):
        raise RuntimeError('unresolved marker; preserve and inspect')
    if any(work.rglob('*.partial')):
        raise RuntimeError('unfinished original')
    if {path.name for path in (work / 'branches').iterdir() if path.is_dir()} != {case['id'] for case in ev.cases()}:
        raise ValueError('missing or extra unregistered scientific branch')
    plan = m.read(work / 'selection.json')
    rows = []
    for world in range(2):
        selection = plan['worlds'][world]
        if selection['world'] != world:
            raise ValueError('world index differs')
        eligible = sorted(row['body'] for row in selection['rows'] if row['valid'])
        audit_selection(work / 'parents' / f'w{world}' / 'states' / '20000000', selection)
        arms, results = {}, {}
        for case in (case for case in ev.cases() if case['world'] == world):
            result, primary = branch(work, case, selection)
            name = f'{case["mode"]}-{case["operation"]}'
            results[name], arms[name] = result, primary
        restored = {}
        for mode in ev.MODES:
            a, b = results[f'{mode}-sham'], results[f'{mode}-restored']
            restored[mode] = all(a[key]['canonical_sha256'] == b[key]['canonical_sha256']
                                 for key in ('initial', 'primary', 'final')) and a['trajectory_sha256'] == b['trajectory_sha256']
        score = independent_scores(arms, eligible, restored)
        rows.append({'world': world, 'eligible': eligible, 'restoration_exact': restored, **score})
    qualified = all(row['measurement_valid'] for row in rows)
    verdict = 'PASS' if all(row['verdict'] == 'PASS' for row in rows) else 'FAIL' if qualified else 'MEASUREMENT_NOT_QUALIFIED'
    return {'schema': 'threemind.m6-historical-audit/1', 'passed_integrity': True,
            'read_only': True, 'Core_constructed': False, 'independent_new_origins': 0,
            'historical_environment_replays': 2, 'worlds': rows, 'verdict': verdict}
