"""Preregistered counts and calibration rules; no Core imports."""
import statistics as st

DELAYS = (1, 30, 60, 300)
MODES = ('default', 'stability')


def first_two(values, threshold):
    run = 0
    for i, value in enumerate(values, 1):
        run = run+1 if value > threshold else 0
        if run >= 2:
            return i
    return 17


def calibrate(rows):
    selections = {}
    for mode in MODES:
        group = [r for r in rows if r['mode'] == mode]
        assert len(group) == 4 and all(len(r['values']) == 16 for r in group)
        early = max(v for r in group for v in r['values'][:3])
        late = min(v for r in group for v in r['values'][-4:])
        threshold = (early+late)/2 if late-early > 1e-5 else None
        rounds = [] if threshold is None else [first_two(r['values'], threshold) for r in group]
        valid = threshold is not None and all(4 <= n <= 14 for n in rounds)
        selections[mode] = {'valid': valid, 'early_max': early, 'late_min': late,
                            'threshold': threshold if valid else None,
                            'calibration_rounds': rounds,
                            'reason': 'resolved learning course' if valid else 'no valid separation from the measurement floor'}
    return selections


def evaluate(units, calibration):
    assert len(units) == 64
    results = {}
    adverse = []
    for mode in MODES:
        cohorts = {}
        for delay in DELAYS:
            group = [u for u in units if u['mode'] == mode and u['delay'] == delay]
            assert len(group) == 8 and {u['origin'] for u in group} == set(range(8))
            origins = []
            for u in sorted(group, key=lambda x: x['origin']):
                separation, transient, retrieved, savings, baseline = [], [], [], [], []
                for h in u['histories']:
                    sign = 1 if h['history'] == 0 else -1
                    t = h['tests']
                    strong = sign*t['strong']['first'] > 1e-4
                    elicited = strong or sign*t['joint']['first'] > 1e-4
                    retrieved.append(elicited)
                    separation.append(len(h['target_edges']) == 2 and abs(t['weak']['first']) <= 1e-9
                                      and elicited and abs(t['none']['first']) <= 1e-9)
                    transient.append(strong and abs(t['strong']['late_mean']) <= 1e-9)
                    if calibration[mode]['valid']:
                        threshold = calibration[mode]['threshold']
                        savings.append(h['untrained']['rounds']-h['relearning']['rounds'])
                        baseline.append(sign*t['strong']['early_integral']/.201 > threshold)
                origins.append({'origin': u['origin'], 'retrieval_both_histories': all(retrieved),
                                'separation': all(separation), 'transient': all(transient),
                                'savings': st.mean(savings) if savings else None,
                                'already_expressed_at_calibrated_standard': baseline,
                                'structural_counts': [{'history':h['history'],
                                    'visible_target_edges':len(h['target_edges']),
                                    'stored_target_edges':len(h['stored_target_edges']) if 'stored_target_edges' in h else None,
                                    'sleeping_target_edges':h.get('sleeping_target_edges')}
                                    for h in u['histories']]})
            sep = sum(o['separation'] for o in origins)
            transient_n = sum(o['transient'] for o in origins)
            retrieval_n = sum(o['retrieval_both_histories'] for o in origins)
            if mode == 'default' and delay in (1, 30, 60) and retrieval_n < 6:
                adverse.append({'mode': mode, 'delay': delay, 'retrieved_origins': retrieval_n})
            speed = {'verdict': 'MEASUREMENT_UNAVAILABLE', 'calibration_valid': calibration[mode]['valid']}
            if calibration[mode]['valid']:
                floor = sum(any(h['untrained']['rounds'] == 2 for h in u['histories']) for u in group)
                censored = sum(any(h['untrained']['rounds'] == 17 for h in u['histories']) for u in group)
                values = [o['savings'] for o in origins]
                mean = st.mean(values)
                positives = sum(v > 0 for v in values)
                sensitive = floor <= 2 and censored <= 2
                speed.update(verdict=('INSUFFICIENT_SENSITIVITY' if not sensitive else
                                      'PASS' if mean >= 2 and positives >= 6 else 'FAIL'),
                             floor_origins=floor, censored_origins=censored,
                             mean_saved_rounds=mean, positive_origins=positives, values=values)
            cohorts[str(delay)] = {'origins': origins, 'retrieved_origins': retrieval_n,
                'separation_count': sep, 'separation_verdict': 'PASS' if sep >= 6 else 'FAIL',
                'transient_count': transient_n, 'transient_verdict': 'PASS' if transient_n >= 6 else 'FAIL',
                'relearning': speed}
        results[mode] = {'cohorts': cohorts,
                         'separation_verdict': 'PASS' if any(c['separation_count'] >= 6 for c in cohorts.values()) else 'FAIL',
                         'transient_verdict': 'PASS' if any(c['transient_count'] >= 6 for c in cohorts.values()) else 'FAIL'}
    return {'independent_origins': 32, 'origins_per_delay': 8, 'configuration_units': 64,
            'configurations': results, 'scientific_stop': bool(adverse), 'new_adverse_retrieval': adverse}
