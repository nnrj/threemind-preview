"""Preregisterable counterfactual metrics for two historical E53 worlds.

No scores are fed to a world, and bodies/frames are not independent N.
"""
import math
import numpy as np

MODES=('live','muted')
OPERATIONS=('sham','target','matched','restored')
MIN_BASELINE_RMS=.01
MIN_TARGET_ATTENUATION=.25
MIN_SELECTIVITY=.20
MIN_ELIGIBLE=8
PRIMARY_STEPS=50


def action_matrix(rows,eligible,start_us=20_000_000,period_us=20_000):
    """Actual pre-physics actions; absent/dead bodies have zero motor output."""
    ids=tuple(sorted(map(int,eligible)))
    if len(ids)!=len(set(ids)) or not ids:raise ValueError('unique nonempty frozen body set required')
    selected=[r for r in rows if start_us<=r['action_time_us']<start_us+1_000_000]
    expected=list(range(start_us,start_us+1_000_000,period_us))
    if [r['action_time_us'] for r in selected]!=expected or len(selected)!=PRIMARY_STEPS:
        raise ValueError('incomplete, duplicate or unordered primary action window')
    values=np.asarray([[r['actions'].get(str(i),[0.,0.,0.]) for i in ids] for r in selected],dtype=float)
    if values.shape!=(PRIMARY_STEPS,len(ids),3) or not np.isfinite(values).all() or (np.abs(values)>1+1e-12).any():
        raise ValueError('invalid motor action array')
    return values


def world_result(arms,eligible,restoration_exact):
    """Close the numerical target without changing the frozen denominator."""
    if set(arms)!={f'{mode}-{op}' for mode in MODES for op in OPERATIONS}:
        raise ValueError('complete 2 x 4 factorial required')
    if set(restoration_exact)!=set(MODES):raise ValueError('both restoration checks required')
    matrices={name:action_matrix(rows,eligible) for name,rows in arms.items()}
    differences={op:float(np.sqrt(np.mean((matrices['live-'+op]-matrices['muted-'+op])**2))) for op in OPERATIONS}
    # The denominator is fixed before intervention, never surviving-body-only.
    baseline=differences['sham']
    valid=len(eligible)>=MIN_ELIGIBLE and baseline>=MIN_BASELINE_RMS and all(restoration_exact.values())
    attenuations={op:1.-differences[op]/baseline if baseline>0 else None for op in ('target','matched','restored')}
    selectivity=attenuations['target']-attenuations['matched'] if baseline>0 else None
    reached=valid and attenuations['target']>=MIN_TARGET_ATTENUATION and selectivity>=MIN_SELECTIVITY
    return {'eligible_bodies':len(eligible),'historical_environment_replays':1,'steps_per_body':PRIMARY_STEPS,
            'partner_action_rms':differences,'attenuation':attenuations,'selectivity':selectivity,
            'measurement_valid':valid,'restoration_exact':restoration_exact,
            'verdict':'PASS' if reached else 'FAIL' if valid else 'MEASUREMENT_NOT_QUALIFIED',
            'criteria':{'minimum_eligible':MIN_ELIGIBLE,'minimum_baseline_rms':MIN_BASELINE_RMS,
                        'minimum_target_attenuation':MIN_TARGET_ATTENUATION,'minimum_selectivity':MIN_SELECTIVITY}}


def overall(worlds):
    if len(worlds)!=2:raise ValueError('exactly two preserved historical worlds required')
    valid=all(w['measurement_valid'] for w in worlds)
    return {'historical_environment_replays':2,'independent_new_origins':0,
            'shared_founder_lineages':True,'worlds':worlds,
            'verdict':'PASS' if all(w['verdict']=='PASS' for w in worlds) else 'FAIL' if valid else 'MEASUREMENT_NOT_QUALIFIED',
            'scope':'specified cross-sensory edge subsets and partner-dependent motor output in the two archived /2 worlds'}
