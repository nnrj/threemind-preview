"""M5 curriculum and causal copies with paired temporal/endpoint personal readers."""
import readout_rig as g
m = g.m

def save(folder, name, subject):
    path = folder / (name + '.json.gz')
    return {'path': path.name, **m.original(path, subject.save(), compressed=True)}

def measured_exam(subject, folder, prefix, history, dose=0.8, observed=False):
    rows = []
    cues = list(zip(g.NEW, g.OLD))
    if subject.seed % 2:
        cues = cues[::-1]
    for pair in cues:
        for cue in pair:
            row = g.question(subject, cue, dose, observed)
            row.update(label=g.label(cue, history), group='new' if cue in g.NEW else 'old')
            row['checkpoint'] = save(folder, f'{prefix}-q{len(rows):02d}', subject)
            rows.append(row)
    return rows

def unit(folder, origin):
    p = g.Subject(1056100 + origin)
    p.tick(0, [{'K': 0.2}])
    save(folder, 'birth', p)
    calibration = g.calibrate(p)
    save(folder, 'old-calibrated', p)
    early = measured_exam(p, folder, 'early', 0)
    save(folder, 'parent-before-new-teaching', p)
    histories = []
    for history in (0, 1):
        cases = {}
        for enabled in (True, False):
            learner = p.fork(f'h{history}-plasticity-{enabled}')
            config_receipt = g.plasticity(learner, enabled)
            save(folder, f'h{history}-plasticity-{enabled}-start', learner)
            teaching = g.teach(learner, history)
            save(folder, f'h{history}-plasticity-{enabled}-taught', learner)
            for arm in ('sham', 'target', 'matched', 'restored') if enabled else ('plasticity-off',):
                child = learner.fork(arm)
                receipt = g.mask(child, arm)
                save(folder, f'h{history}-{arm}-initial', child)
                rows = measured_exam(child, folder, f'h{history}-{arm}', history)
                cases[arm] = {'rows': rows, 'mask': receipt, 'teaching': teaching, 'configuration': config_receipt}
                if arm == 'sham':
                    r0 = {'full': child.reader.save(), 'ports': child.port_reader.save()}
                    endpoint_r0 = {'full': child.endpoint_reader.save(), 'ports': child.endpoint_port_reader.save()}
                    training = [r for r in rows if r['group'] == 'new']
                    fitted = child.fork('continued-personal-reader')
                    fitted.reader.learn([{'features': r['features'], 'label': r['label']} for r in training])
                    fitted.port_reader.learn([{'features': r['port_features'], 'label': r['label']} for r in training])
                    fitted.endpoint_reader.learn([{'features': r['endpoint_features'], 'label': r['label']} for r in training])
                    fitted.endpoint_port_reader.learn([{'features': r['endpoint_port_features'], 'label': r['label']} for r in training])
                    r1 = {'full': fitted.reader.save(), 'ports': fitted.port_reader.save()}
                    endpoint_r1 = {'full': fitted.endpoint_reader.save(), 'ports': fitted.endpoint_port_reader.save()}
                    save(folder, f'h{history}-continued-reader-start', fitted)
                    fixed = child.fork('fixed-reader-heldout')
                    save(folder, f'h{history}-fixed-heldout-start', fixed)
                    heldout = {}
                    for name, life in (('fixed', fixed), ('continued', fitted)):
                        heldout[name] = []
                        for dose in (0.85, 0.95):
                            heldout[name] += measured_exam(life, folder, f'h{history}-heldout-{name}-{dose}', history, dose)
                    cases[arm].update(readers_before=r0, readers_after=r1, endpoint_readers_before=endpoint_r0, endpoint_readers_after=endpoint_r1, heldout=heldout, heldout_core_equal=fixed.save()['core'] == fitted.save()['core'])
        histories.append({'history': history, 'cases': cases})
    result = {'package': 'M5', 'origin': origin, 'seed': p.seed, 'calibration': calibration, 'early': early, 'histories': histories}
    result['integrity_valid'] = all((h['cases']['sham']['heldout_core_equal'] for h in histories))
    result['matching_valid'] = all((h['cases']['sham']['mask']['matching_valid'] and h['cases']['sham']['teaching']['old_new_activity_residual'] <= 0.02 for h in histories))
    result['valid'] = result['integrity_valid'] and result['matching_valid']
    return result
