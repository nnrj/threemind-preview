"""Explicit, cue-specific and reversal-following expression outcomes."""
from collections import defaultdict
import json

from experiment import HERE, WORK, SEEDS, read_json, new_json

INSTRUMENTS=('transformer','prototype','raw_prototype')
REGIMES=('individual','shared','developmental','history-cold','direct')


def decoded():
    rows=[]
    for path in sorted((WORK/'decoded').glob('*.json')):
        value=read_json(path)
        regime=value['model'].split('-s')[0]
        rows.extend(row|{'regime':regime,'training_ids':value['training_ids']} for row in value['rows'])
    return rows


def analyze():
    rows=decoded()
    baseline={(r['regime'],r['seed'],r['modality'],r['condition'],r['seconds'],r['intervention']):r
              for r in rows if r['item']<0 and r['split']=='test'}
    groups=defaultdict(lambda:{'count':0,'correct':0,'cue_specific_correct':0,'blank':0})
    lookup={}
    for r in rows:
        if r['split']!='test' or r['intervention']!='none':continue
        lookup[(r['regime'],r['seed'],r['modality'],r['condition'],r['seconds'],r['item'],r['variant'])]=r
        b=baseline[(r['regime'],r['seed'],r['modality'],r['condition'],r['seconds'],r['intervention'])]
        for instrument in INSTRUMENTS:
            key=(r['regime'],r['seed'],r['modality'],r['condition'],r['seconds'],r['item']<0,instrument)
            out=r[instrument]['text'];correct=out==r['target']
            g=groups[key];g['count']+=1;g['correct']+=correct;g['blank']+=out==''
            g['cue_specific_correct']+=correct and (r['item']<0 or out!=b[instrument]['text'])
    summary=[dict(zip(('regime','seed','modality','condition','seconds','no_cue','instrument'),key,strict=True))|value
             for key,value in groups.items()]
    paired=[]
    for regime in REGIMES:
        for seed in SEEDS:
            for modality in ('vision','words'):
                for seconds in (532,592):
                    for item in range(4):
                        for variant in ((0,1) if modality=='vision' else (9,)):
                            a=lookup.get((regime,seed,modality,'normal',266,item,variant))
                            b=lookup.get((regime,seed,modality,'reversal',seconds,item,variant))
                            if not a or not b:continue
                            ba=baseline[(regime,seed,modality,'normal',266,'none')]
                            bb=baseline[(regime,seed,modality,'reversal',seconds,'none')]
                            for instrument in INSTRUMENTS:
                                correct=a[instrument]['text']==a['target'] and b[instrument]['text']==b['target']
                                paired.append({'regime':regime,'seed':seed,'modality':modality,'seconds':seconds,
                                    'item':item,'variant':variant,'instrument':instrument,'before':a[instrument]['text'],
                                    'after':b[instrument]['text'],'expected_before':a['target'],'expected_after':b['target'],
                                    'correct':correct,'cue_specific_correct':correct and a[instrument]['text']!=ba[instrument]['text'] and b[instrument]['text']!=bb[instrument]['text'],
                                    'before_case':a['id'],'after_case':b['id']})
    joint=defaultdict(lambda:{'count':0,'correct':0,'cue_specific_correct':0})
    for r in paired:
        g=joint[(r['regime'],r['seed'],r['modality'],r['seconds'],r['instrument'])]
        g['count']+=1;g['correct']+=r['correct'];g['cue_specific_correct']+=r['cue_specific_correct']
    joint_summary=[dict(zip(('regime','seed','modality','seconds','instrument'),key,strict=True))|value for key,value in joint.items()]
    return {'summary':summary,'paired':paired,'joint_summary':joint_summary,'source_instances':list(SEEDS),
        'primary_gate':{'vision':6,'words':3,'seeds_required':2},
        'interpretation':'passive activity-to-language; active speech selection not tested'}


def compact(result):
    grouped=defaultdict(lambda:{'correct':0,'n':0,'specific':0})
    for row in result['summary']:
        if row['seconds'] not in (266,326,532,592):continue
        key=(row['regime'],row['modality'],row['condition'],row['seconds'],row['no_cue'],row['instrument'])
        g=grouped[key];g['correct']+=row['correct'];g['n']+=row['count'];g['specific']+=row['cue_specific_correct']
    return [dict(zip(('regime','modality','condition','seconds','no_cue','instrument'),key,strict=True))|v for key,v in grouped.items()]


if __name__=='__main__':
    result=analyze()
    print(json.dumps({'summary':[r for r in compact(result) if not r['no_cue'] and r['instrument']=='transformer'],
                      'joint':result['joint_summary']},ensure_ascii=False))
