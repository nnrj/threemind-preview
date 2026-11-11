"""Summarize only the twelve preregistered cases; never run or train a model."""
import csv
import io
from pathlib import Path
from probe import read, write, ResearchStorage, load_env, HERE, KEY


def main():
    load_env();work=ResearchStorage().workspace_path(HERE.name)
    complete=read(work/'complete.json');plan=read(work/'plan.json')
    rows=[];arms={}
    for arm in plan['arms']:
        reader=read(work/'arms'/arm/'reader-probes.json')
        readers={(r['question_id'],r['stage']):r for r in reader}
        counts=dict(n=12,normal_correct=0,silence_correct=0,rescue_correct=0,
                    changed_answers=0,correct_to_wrong=0,wrong_to_correct=0,
                    correct_to_correct=0,wrong_to_wrong=0,all_input_equal=True,all_rescue_activity_equal=True)
        cases=[]
        for item in plan['questions']:
            q=item['task'];qid=q['question_id']
            trials={mode:read(work/'arms'/arm/qid/mode/'result.json') for mode in plan['conditions']}
            normal,silence,rescue=(trials[m] for m in ('normal','silence','rescue'))
            assert normal['same_features_as_original'] and rescue['same_features_as_original']
            assert normal['input_sha256']==silence['input_sha256']==rescue['input_sha256']
            assert normal['reader_sha256']==silence['reader_sha256']==rescue['reader_sha256']
            assert silence['old_edges_remaining_unsilenced']==0
            assert rescue['selected']==normal['selected']
            transition=('correct' if normal['correct'] else 'wrong')+'_to_'+('correct' if silence['correct'] else 'wrong')
            counts[transition]+=1
            counts['changed_answers']+=int(normal['selected']!=silence['selected'])
            for mode,t in trials.items():counts[mode+'_correct']+=int(t['correct'])
            row=dict(arm=arm,question_id=qid,shape=q['shape'],color=q['color'],attribute=q['attribute'],
                offset_x=q['offset'][0],offset_y=q['offset'][1],label=q['label'],transition=transition,
                normal=normal['word'],silence=silence['word'],rescue=rescue['word'],
                probability_normal=normal['true_probability'],probability_silence=silence['true_probability'],
                probability_rescue=rescue['true_probability'],
                birth_reader=readers[qid,'birth']['word'],initial_reader=readers[qid,'initial_fit']['word'],
                final_reader=readers[qid,'final_fit']['word'],zero_input=readers[qid,'zero_input']['word'],
                normal_sent=normal['transport_delta']['sent'],silence_sent=silence['transport_delta']['sent'],
                silence_new_edges=silence['new_edges'],silence_associative_sum=silence['activity_sum_by_field']['associative'])
            rows.append(row);cases.append(row)
        counts['reader_correct']={stage:sum(r['correct'] for r in reader if r['stage']==stage)
                                  for stage in ('birth','initial_fit','final_fit','zero_input')}
        counts['reader_initial_to_final_changed']=sum(readers[q['task']['question_id'],'initial_fit']['selected']!=
            readers[q['task']['question_id'],'final_fit']['selected'] for q in plan['questions'])
        counts['reader_initial_to_final_corrected']=sum(not readers[q['task']['question_id'],'initial_fit']['correct'] and
            readers[q['task']['question_id'],'final_fit']['correct'] for q in plan['questions'])
        counts['reader_initial_to_final_regressed']=sum(readers[q['task']['question_id'],'initial_fit']['correct'] and
            not readers[q['task']['question_id'],'final_fit']['correct'] for q in plan['questions'])
        counts['new_edges_range']=[min(r['silence_new_edges'] for r in cases),max(r['silence_new_edges'] for r in cases)]
        counts['transport_sent_suppression']=1-sum(r['silence_sent'] for r in cases)/sum(r['normal_sent'] for r in cases)
        arms[arm]=counts
    summary=dict(schema='threemind.e67-causal-summary/1',source=KEY,arms=arms,cases=rows,
        scope='Purposively selected post-outcome diagnoses; two individuals, not 24 independent subjects. No contribution percentages.',
        source_unchanged=complete['sources_unchanged'])
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with ResearchStorage().writer('research:e67-causal-probes-20261012'):
        write(work/'analysis/paired-cases.csv',stream.getvalue().encode('utf-8-sig'))
        write(work/'analysis/summary.json',summary)
        write(work/'source-reference/analyze.py',Path(__file__).read_bytes())
    import json
    print(json.dumps(arms,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
