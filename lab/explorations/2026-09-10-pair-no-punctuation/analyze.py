"""Complete window-end rankings, with predeclared external pairing references."""
import importlib.util
import json
from collections import Counter,defaultdict

from run import HERE,ROOT,WORK,META,encoded,sha

path=HERE.parent/'2026-09-10-temporal-repetition/analyze.py'
loader=importlib.util.spec_from_file_location('prior_temporal_analysis',path)
base=importlib.util.module_from_spec(loader);loader.loader.exec_module(base)


def expected_answer(arm,group,cue):
    return {'甲是':'松子','乙是':'铃铛','甲':'松子','乙':'铃铛','松子':'甲','铃铛':'乙'}[cue]


base.expected_answer=expected_answer


def analyze():
    if (HERE/'analysis.json').exists():raise RuntimeError('Existing analysis cannot be overwritten')
    result=base.analyze()
    maps={(m['seed'],m['group']):m for m in json.loads((HERE/'mapping.json').read_bytes())}
    keyed={(c['calibration_id'],c['case_id']):c for c in result['cases']}
    with (HERE/'node-rankings.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);case=keyed[row['calibration_id'],row['case_id']]
            nodes=row['rankings']['end_activation']
            channels={n['channel']:n for n in nodes if n['channel'] is not None}
            masks=maps[(case['seed'],case['group'])]['contextual']['masks']
            context_scores=base.scores(masks,channels)
            for term,score in context_scores.items():
                observed={int(c):w for c,w in masks[term].items() if int(c) in channels}
                score['observed_only_mean']=(sum(w*channels[c]['last_activation'] for c,w in observed.items())
                                             /sum(observed.values())) if observed else None
            case['context_scores']=context_scores
            case['context_outcome']=base.outcome(context_scores,expected_answer(case['arm'],case['group'],case['cue']))
            case['primary_pairing_status']=(case['context_outcome']['classification'] if case['converged']
                                            else 'not_a_converged_result')
            case['highest_activation_tie_count']=sum(n['rank']==1 for n in nodes)
            case['ranking_reference']=dict(file='node-rankings.jsonl',calibration_id=case['calibration_id'],
                                           case_id=case['case_id'])
    grouped=defaultdict(list)
    for c in result['cases']:grouped[(c['stage'],c['dose'],c['arm'])].append(c)
    result['pair_summaries']=[dict(stage=stage,dose=dose,arm=arm,n=len(cases),
        classifications=dict(Counter(c['classification'] for c in cases)),
        context_outcomes_among_converged=dict(Counter(c['context_outcome']['classification']
              for c in cases if c['converged'])),
        context_outcomes_all_windows=dict(Counter(c.get('context_outcome',{}).get('classification','not_observed')
              for c in cases))) for (stage,dose,arm),cases in grouped.items()]
    result['instrumentation_analysis_dependencies']={path.relative_to(ROOT).as_posix():sha(path)}
    result['registered_primary']='actual converged windows, full endpoint activation ranking with ties retained'
    result['secondary_reference']='template and contextual-channel statistics remain external annotations, not decoded replies'
    (HERE/'analysis.json').write_bytes(encoded(result))
    print(encoded({'cases':len(result['cases']),'summaries':result['pair_summaries']}).decode())
    return result


if __name__=='__main__':analyze()
