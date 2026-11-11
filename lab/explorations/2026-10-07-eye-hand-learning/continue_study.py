"""Registered E60 stages, one compute worker and immutable case identities."""
import argparse
from experiment import study, fit, evaluate, correct, teach, demonstrations, WORK, read_json, new_json


def selection():
    return read_json(WORK/'selection.json')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['correction', 'confirmation', 'causality', 'nose'])
    args = p.parse_args(); s = study()
    try:
        if args.stage == 'correction':
            for organization in ('shared', 'separate'):
                fit(s, 'B-teach', organization, readout_version=2)
            base = 'C-fit-B-teach-shared-activity-fit2'
            candidates = [base, base+'-v2']
            selected = min(candidates, key=lambda n: read_json(WORK/'cases'/n/'result.json')['fit']['validation_mse'])
            version = read_json(WORK/'cases'/selected/'result.json')['fit']['readout_version']
            if not (WORK/'selection.json').exists():
                new_json(WORK/'selection.json', {'model': selected, 'reader_version': version,
                    'criterion': 'shared primary; architecture selected only by held-out demonstration MSE'})
            elif selection()['model'] != selected: raise RuntimeError('do not overwrite selection')
            evaluate(s, 'B-teach', 'C-fit-B-teach-separate-activity-fit2', count=16)
            if selected != base: evaluate(s, 'B-teach', selected, count=16)
            evaluate(s, 'B-teach', selected, cue='visible', count=8)
            correct(s, 'B-teach', selected, count=12)
            fit(s, 'B-teach', correction='E-correct-B-teach', readout_version=version)
        else:
            choice = selection(); old = choice['model']; version = choice['reader_version']
            new = 'C-fit-B-teach-shared-activity-fit2-E-correct-B-teach'+('-v2' if version == 2 else '')+'-val2'
            if args.stage == 'confirmation':
                demonstrations(s, 'E-correct-B-teach')
                fit(s, 'B-teach', correction='E-correct-B-teach', readout_version=version, mixed_validation=True)
                # All four cells on the same unused layouts; no further tuning.
                for source in ('B-teach', 'E-correct-B-teach'):
                    for model in (old, new):
                        evaluate(s, source, model, split='confirmation', count=12, world_reference='B-teach')
            elif args.stage == 'causality':
                source = 'E-correct-B-teach'
                for mode in ('empty', 'silence', 'rescue'):
                    evaluate(s, source, new, mode=mode, split='confirmation', count=12, world_reference='B-teach')
                # Same independent layouts, explicitly not a consciousness route.
                fit(s, 'B-teach', kind='incoming', correction='E-correct-B-teach', readout_version=version, mixed_validation=True)
                bypass = new.replace('-activity-', '-incoming-')
                evaluate(s, source, bypass, kind='incoming', split='confirmation', count=12, world_reference='B-teach')
            elif args.stage == 'nose':
                # Independent head-fixed-reference comparison; no transfer of a
                # reader trained on a different optical world into the comparison.
                teach(s, nose=True); demonstrations(s, 'B-teach-nose')
                fit(s, 'B-teach-nose', readout_version=version)
                model = 'C-fit-B-teach-nose-shared-activity-fit2'+('-v2' if version == 2 else '')
                evaluate(s, 'B-teach-nose', model, count=16)
    finally: s.db.close()


if __name__ == '__main__': main()
