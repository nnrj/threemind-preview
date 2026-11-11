"""One final summary from small case receipts, not repeated state/archive audits."""
import json
from collections import defaultdict

from experiment import HERE, WORK, analyse, read_json

from lab.tools.service_study import new_json


def expression_summary():
    rows=[];observations=[]
    for path in (WORK/'expression').glob('*.json'):
        data=read_json(path);kind=data['modality'];seed=data['seed']
        base={(r['source'],r['seconds'],r['window']):r for r in data['rows'] if r['cue_index']==-1 and r['intervention']=='none'}
        for row in data['rows']:
            direction='vision' if 0<=row['cue_index']<8 else 'words' if row['cue_index']>=8 else None
            if direction!=kind or row['intervention']!='none':continue
            parent=read_json(WORK/'cases'/row['source']/'definition.json')
            from lab.tools.language_teaching_world import WORDS
            expected=(WORDS if kind=='vision' else parent['names'])[row['target']]+'。'
            background=base[(row['source'],row['seconds'],row['window'])]['output']['text']
            observations.append(row|{'seed':seed,'direction':kind,'expected':expected,'uncued_text':background,
                'cue_specific_correct':row['output']['text']==expected and background!=expected})
    trials=defaultdict(list)
    for r in observations:trials[(r['source'],r['seconds'],r['cue_index'])].append(r)
    pairs=defaultdict(dict)
    for group in trials.values():
        r=group[0]
        row={k:r[k] for k in ('source','seed','direction','parameter','condition','seconds','cue_index')}
        row.update(correct=any(x['cue_specific_correct'] for x in group),
                   outputs=[x['output']['text'] for x in group],uncued=[x['uncued_text'] for x in group])
        rows.append(row)
        if row['condition'] in ('normal','reversed'):
            pairs[(r['parameter'],r['seed'],r['direction'],r['seconds'],r['cue_index'])][r['condition']]=row
    return {'rows':rows,'pairs':[{'parameter':k[0],'seed':k[1],'direction':k[2],'seconds':k[3],'cue_index':k[4],
        'correct':v['normal']['correct'] and v['reversed']['correct']} for k,v in pairs.items() if len(v)==2],
        'criterion':'at least one of four half-second windows correct and different from aligned no-cue text; all raw outputs retained'}


def main():
    target=HERE/'results.json'
    if target.exists():raise RuntimeError('final results already frozen')
    cases=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    compute=sum(r['wall_seconds'] for r in cases)
    compute+=sum(read_json(p).get('wall_seconds',0) for p in (WORK/'models').glob('*.json')
                 if not p.name.endswith('.training.json') and not read_json(p).get('reused'))
    compute+=read_json(HERE/'continuous-results.json').get('analysis_wall_seconds',0)
    result={'schema':'E45-results/1','completed_cases':len(cases),'recorded_compute_seconds':compute,
            'input_selection':read_json(WORK/'input-selection.json'),'parameter_selection':read_json(WORK/'parameter-selection.json'),
            'calibration':analyse(),'formal':analyse('formal'),'composition':analyse('composition'),
            'expression':expression_summary()}
    for key in ('visual-reader-validation','visual-reader-formal','expression-validation','formal-interventions','composition-interventions','continuous-results','component-results','encoding-diagnostics','reciprocal-effects','structure-diagnostics','pattern-results'):
        result[key]=read_json(HERE/(key+'.json'))
    counts=defaultdict(int)
    for case in cases:counts[case['kind']]+=1
    result['case_types']=dict(counts)
    new_json(target,result)
    print(json.dumps({'completed':len(cases),'minutes':round(compute/60,2),'formal':result['formal']['summary'],
                      'composition':result['composition']['summary']},ensure_ascii=False))


if __name__=='__main__':main()
