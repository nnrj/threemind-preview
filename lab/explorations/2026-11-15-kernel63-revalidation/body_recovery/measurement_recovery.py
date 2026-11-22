"""Prespecified E22 response-transfer and retention summaries; no Core."""
from collections import Counter
import itertools
from statistics import mean

SEEDS=(930101,930102,930103,930104)
GROUPS=('none','N','S','SN','W','WN','WS','WSN')
EPS=1e-6


def direction(value):return 'taught' if value>EPS else 'opposite' if value < -EPS else 'unresolved'


def summarize(cut,recovery):
    assert len(cut)==256 and len(recovery)==96
    ci={(r['seed'],r['mode'],r['learn'],r['groups'],r['sign']):r for r in cut}
    ri={(r['seed'],r['mode'],r['learn'],r['delay_s'],r['sign']):r for r in recovery}
    assert len(ci)==256 and len(ri)==96
    transfers=[];cells=[];primary=[]
    for seed,mode,learn,groups,sign in itertools.product(SEEDS,('full','no_imu'),('01','11'),GROUPS,(1,-1)):
        recipient=ci[(seed,mode,learn,'none',sign)]['margin']
        donor=ci[(seed,mode,'11' if learn=='01' else '01','none',sign)]['margin']
        after=ci[(seed,mode,learn,groups,sign)]['margin']
        before_distance=abs(donor-recipient);after_distance=abs(donor-after)
        category=('not_identifiable' if before_distance<=EPS else 'donor_reproduced' if after_distance<=EPS else
                  'partial_transfer' if after_distance<before_distance-EPS else 'no_movement_toward_donor')
        transfers.append({'seed':seed,'mode':mode,'learn':learn,'groups':groups,'sign':sign,
            'recipient':recipient,'donor':donor,'after':after,'category':category,
            'before_distance':before_distance,'after_distance':after_distance,
            'signed_transfer_fraction':None if before_distance<=EPS else (after-recipient)/(donor-recipient)})
    for mode,learn,groups in itertools.product(('full','no_imu'),('01','11'),GROUPS):
        selected=[r for r in transfers if (r['mode'],r['learn'],r['groups'])==(mode,learn,groups)]
        cells.append({'mode':mode,'learn':learn,'groups':groups,'responses':len(selected),
            'mean_margin':mean(r['after'] for r in selected),
            'directions':dict(Counter(direction(r['after']) for r in selected)),
            'transfer_classes':dict(Counter(r['category'] for r in selected)),
            'mean_distance_before':mean(r['before_distance'] for r in selected),
            'mean_distance_after':mean(r['after_distance'] for r in selected)})
    for learn in ('01','11'):
        selected=[r for r in transfers if r['mode']=='full' and r['learn']==learn and r['groups']=='W']
        blocks=[]
        for seed in SEEDS:
            pair=[r for r in selected if r['seed']==seed];assert len(pair)==2
            blocks.append({'seed':seed,'effect':mean(r['after']-r['recipient'] for r in pair),
                'donor_recipient_distance':mean(r['before_distance'] for r in pair)})
        differences=[r['effect'] for r in blocks]
        primary.append({'learn':learn,'blocks':blocks,'mean_difference':mean(differences),
            'contrast_identifiable':sum(r['donor_recipient_distance']>EPS for r in blocks)>=3,
            'consistent_effect':max(sum(d>EPS for d in differences),sum(d < -EPS for d in differences))>=3})
    waiting=[]
    for mode,learn,delay in itertools.product(('full','no_imu'),('01','11'),(10,30,60)):
        blocks=[]
        for seed in SEEDS:
            margins=[ri[(seed,mode,learn,delay,sign)]['margin'] for sign in (1,-1)]
            blocks.append({'seed':seed,'margins':margins,'passed':all(v>EPS for v in margins)})
        waiting.append({'mode':mode,'learn':learn,'delay_s':delay,'blocks':blocks,
            'mean_margin':mean(v for b in blocks for v in b['margins']),
            'passed_blocks':sum(b['passed'] for b in blocks),'passed':sum(b['passed'] for b in blocks)>=3})
    identifiable=any(r['contrast_identifiable'] for r in primary)
    return {'material_blocks':4,'cut_cells':cells,'transfers':transfers,'primary_weight_effects':primary,
        'weight_effect_confirmed':any(r['consistent_effect'] for r in primary),
        'waiting':waiting,'waiting_passed_cells':sum(r['passed'] for r in waiting),
        'measurement_stop':not identifiable,
        'scientific_stop':(identifiable and not any(r['consistent_effect'] for r in primary)) or not all(r['passed'] for r in waiting)}


def check():
    cut=[];recovery=[]
    for seed,mode,learn,groups,sign in itertools.product(SEEDS,('full','no_imu'),('01','11'),GROUPS,(1,-1)):
        value=.1 if learn=='01' else .2
        if 'W' in groups:value=.3-value
        cut.append({'seed':seed,'mode':mode,'learn':learn,'groups':groups,'sign':sign,'margin':value})
    for seed,mode,learn,delay,sign in itertools.product(SEEDS,('full','no_imu'),('01','11'),(10,30,60),(1,-1)):
        recovery.append({'seed':seed,'mode':mode,'learn':learn,'delay_s':delay,'sign':sign,'margin':.05})
    positive=summarize(cut,recovery)
    assert positive['weight_effect_confirmed'] and positive['waiting_passed_cells']==12
    assert not positive['scientific_stop'] and not positive['measurement_stop']
    assert sum(r['category']=='donor_reproduced' for r in positive['transfers'])==128
    for r in cut:r['margin']=.1 if r['learn']=='01' else .2
    negative=summarize(cut,recovery)
    assert negative['scientific_stop'] and not negative['measurement_stop']
    for r in cut:r['margin']=.1
    unresolved=summarize(cut,recovery)
    assert unresolved['measurement_stop'] and not unresolved['scientific_stop']
    return {'passed':True,'created_engines':0,'cut_rows':256,'recovery_rows':96,
            'known_positive_negative_and_unidentifiable_verified':True}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
