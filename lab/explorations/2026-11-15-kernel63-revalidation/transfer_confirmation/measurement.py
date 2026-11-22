"""Original confirmation curriculum and intervention table, with explicit 6.3 apparatus."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent / 'transfer'), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]

import copy
import transfer_rig as g
sys.path.insert(0, str(HERE))
import probe
import spec
import pilot_m2 as m

def save(folder, name, subject):
    path = folder / (name + '.json.gz')
    return {'path': path.name, **m.original(path, subject.save(), compressed=True)}

def unit(folder, origin):
    case = spec.cases()[origin]
    parents, matches = ({}, {})
    for history in (0, 1):
        parent = g.Rig('threemind', case['seed'])
        save(folder, f'birth-h{history}', parent)
        records = g.teaching(parent, history, case['teaching_dose'], delay=case['delay_s'])
        save(folder, f'parent-h{history}-before-settlement', parent)
        g.settle(parent)
        save(folder, f'parent-h{history}', parent)
        parents[history] = parent
        matches[history] = g.matching(parent, records)
        m.original(folder / f'teaching-observation-h{history}.json', records)
    m.original(folder / 'matching.json', matches)
    valid = all((x['passed'] for x in matches.values()))
    result = {'package': 'M1-confirmation', 'origin': origin, 'seed': case['seed'], 'case': case, 'valid': valid, 'matching': matches, 'trials': []}
    if not valid:
        return result
    for history in (0, 1):
        parent, donor = (parents[history], parents[1 - history])
        for arm in spec.ARMS:
            if arm == 'intact':
                child, receipt = (parent.fork(arm), {'arm': arm})
            elif arm == 'sham':
                child, receipt = g.transfer(parent, parent)
            elif arm == 'matched-bundle':
                child, receipt = g.transfer(parent, donor, 'ZW')
            else:
                child, receipt = g.transfer(parent, donor, mode=arm if arm in ('persistent', 'fast') else 'bundle')
                if arm == 'restored':
                    child, _ = g.transfer(child, parent)
            comparable = copy.deepcopy(child.save())
            comparable['branch'] = parent.branch
            if arm in ('intact', 'sham', 'restored') and comparable != parent.save():
                raise RuntimeError('sham/reversal differs from intact whole state')
            m.original(folder / f'h{history}-{arm}-intervention.json', receipt)
            save(folder, f'h{history}-{arm}-initial', child)
            for cue in spec.CUES:
                subject = child.fork(cue)
                outcome = probe.probe(subject, cue)
                checkpoint = save(folder, f'h{history}-{arm}-{cue}-final', subject)
                goal = -1 if history == 0 else 1
                result['trials'].append({'history': history, 'arm': arm, 'cue': cue, 'goal': goal, 'success': outcome['choice'] == goal, 'final_success': outcome['final_gate'] == goal, 'result': outcome, 'checkpoint': checkpoint})
    return result
