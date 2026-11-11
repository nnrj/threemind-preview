"""Read-only causal contrasts and audits; no fitting or Core modifications."""
import argparse
import gzip
import json
import math
from collections import Counter

from common import HERE, WORK, Study, encoded, read_json
from experiment import CONDITIONS, channel_map, parent_name, parents, read_gzip
from threemind_core import StateImage

def case(key):
    return read_json(WORK / 'cases' / key / 'result.json')

def behavior(key):
    return read_gzip(WORK / 'cases' / key / 'behavior.json.gz')

def area(rows, function, lower, upper):
    total = 0.0
    for i, row in enumerate(rows):
        end = rows[i + 1]['relative_us'] if i + 1 < len(rows) else row['relative_us'] + 100_000
        width = max(0, min(end, upper) - max(row['relative_us'], lower)) / 1e6
        if width:
            total += width * function(row)
    return total

def expression():
    output = []
    for champ in parents():
        base = 'expression/' + parent_name(champ) + '/'
        reference = behavior(base + 'normal')['rows']
        for cond in CONDITIONS:
            actual = behavior(base + cond)['rows']
            assert len(actual) == len(reference)
            phases = []
            for start in (0, 5, 10, 15):
                lo, hi = start * 10, (start + 5) * 10
                pairs = list(zip(reference[lo:hi], actual[lo:hi]))
                phases.append({'start_s': start,
                    'control_mae': sum(abs(a['control'] - b['control']) for a,b in pairs) / len(pairs),
                    'control_max': max(abs(a['control'] - b['control']) for a,b in pairs),
                    'opposite_sign_fraction': sum(a['control'] * b['control'] < -1e-10 for a,b in pairs) / len(pairs),
                    'position_mae': sum(abs((a['body']['x'] - b['body']['x'] + .5) % 1 - .5) for a,b in pairs) / len(pairs),
                    'sent_increment': actual[hi - 1]['transport']['sent'] - actual[lo]['transport']['sent']})
            r = case(base + cond)
            output.append({'parent': parent_name(champ), 'condition': cond, 'phases': phases,
                           'region1_fraction': r['extra']['region1_fraction'], 'run': r['id'],
                           'state_equal_normal': r['state_sha256'] == case(base + 'normal')['state_sha256']})
    (WORK / 'expression-analysis.json').write_bytes(encoded(output))
    print(json.dumps(output), flush=True)
    return output

def activation(row, channel):
    return sum(n['activation'] for n in row['nodes'] if int(n['channel']) == int(channel))

def history(*, inherited=False):
    output = []
    for champ in parents():
        symbols = channel_map(champ['seed'])
        for training in (('normal',) if inherited else ('normal', 'blocked')):
            for communication in ('on', 'off'):
                for cue in (('A',) if inherited else ('A', 'C')):
                    values = {}
                    for curriculum in ('P', 'Q'):
                        prefix = f"{'birth-probe' if inherited else 'probe'}/{parent_name(champ)}/{curriculum}/{training}/"
                        rows = behavior(prefix + cue + '/' + communication)['rows']
                        none = behavior(prefix + 'none/' + communication)['rows']
                        assert [r['relative_us'] for r in rows] == [r['relative_us'] for r in none]
                        baseline = {r['relative_us']: r for r in none}
                        phases = []
                        for lower,upper in ((0,1),(1,5),(5,15)):
                            lo,hi = lower * 1_000_000, upper * 1_000_000
                            phases.append({'start_s': lower, 'end_s': upper,
                                'control_auc': area(rows, lambda r:r['control'],lo,hi),
                                'net_control_auc': area(rows, lambda r:r['control']-baseline[r['relative_us']]['control'],lo,hi),
                                'net_B_auc': area(rows, lambda r:activation(r,symbols['B'])-activation(baseline[r['relative_us']],symbols['B']),lo,hi),
                                'net_D_auc': area(rows, lambda r:activation(r,symbols['D'])-activation(baseline[r['relative_us']],symbols['D']),lo,hi)})
                        values[curriculum] = phases
                    output.append({'parent':parent_name(champ), 'training':training, 'communication':communication,
                                   'cue':cue,'values':values,
                                   'P_minus_Q_net_control': [p['net_control_auc']-q['net_control_auc'] for p,q in zip(values['P'],values['Q'])],
                                   'association_contrast': [(p['net_B_auc']-p['net_D_auc']-q['net_B_auc']+q['net_D_auc'])*(1 if cue=='A' else -1)
                                                            for p,q in zip(values['P'],values['Q'])]})
    (WORK / ('birth-analysis.json' if inherited else 'history-analysis.json')).write_bytes(encoded(output))
    compact = [{k:v for k,v in r.items() if k!='values'} for r in output]
    print(json.dumps(compact), flush=True)
    return output

def audit(study):
    rows, counts, windows = [], Counter(), Counter()
    window_rows = []
    for path in sorted((WORK / 'cases').rglob('result.json')):
        r = read_json(path)
        image = StateImage(gzip.decompress((path.parent / 'parent-state.json.gz').read_bytes()))
        assert image.digest == r['state_sha256']
        _, db_image = study.db.load_checkpoint(study.project, r['id'])
        assert db_image.digest == image.digest and db_image.to_dict() == image.to_dict()
        assert not r['extra'].get('budget_stop'), r['key']
        assert image.to_dict()['energy']['unserved_total']==0, r['key']
        counts[r['extra'].get('stage', r['extra'].get('kind','unknown'))] += 1
        events = [json.loads(l) for l in gzip.decompress((path.parent/'events.jsonl.gz').read_bytes()).splitlines()]
        derived = []
        for event in events:
            if event['kind'] == 'temporal_readout':
                w = event['payload']
                windows[w['classification']] += 1
                w['end_activation_ranking'] = sorted(w['nodes'],key=lambda n:(-n['last_activation'],n['node_id']))
                derived.append(w)
        if derived:
            out = path.parent / 'temporal-end-ranking.json.gz'
            if not out.exists():
                with gzip.open(out,'xb') as f: f.write(encoded(derived))
            window_rows.append({'key':r['key'],'counts':dict(Counter(w['classification'] for w in derived))})
        rows.append(r)
    result = {'cases':len(rows),'counts':dict(counts),'compute_seconds':sum(r['wall_seconds'] for r in rows),
              'kernel_unchanged':True,'full_database_state_verified':len(rows),'temporal_classifications':dict(windows),
              'temporal_case_counts':window_rows,'failures':[]}
    (WORK/'analysis.json').write_bytes(encoded(result))
    print(json.dumps({k:v for k,v in result.items() if k!='temporal_case_counts'}),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['expression','history','birth','audit'])
    command=parser.parse_args().command
    if command=='expression': expression()
    elif command=='history': history()
    elif command=='birth': history(inherited=True)
    else:
        study=Study()
        try: audit(study)
        finally: study.db.close()
