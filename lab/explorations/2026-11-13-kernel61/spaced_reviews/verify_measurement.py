"""Check E43 scoring against retained historical observations without replay."""
import argparse
import copy
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_spaced as material
import execute_spaced as execution
import measurement_spaced as measurement


def verify(output):
    assert not output.exists()
    inventory=material.inventory();cases=execution.stages(inventory)
    old=material.read(material.OLD/'analysis-v1.json');texts={}
    for row in old['primary_rows']:
        texts[row['source']+'/probe/'+row['key'] if 'source' in row else
              f"s{row['seed']}-{row['condition']}/probe/{row['key']}",1]=row['decoder']['text']
    for row in old['secondary_cue_dose']:
        texts[f"s{row['seed']}-{row['condition']}/probe/{row['key']}",1]=row['text_at_1']
    scores=measurement.language_scores(cases,texts)
    old_rows={row['key']:row for row in old['primary_rows']}
    assert len(scores['primary_rows'])==400 and len(scores['dose_rows'])==40
    for row in scores['primary_rows']:
        assert row['prediction']==old_rows[row['key'].split('/probe/')[1]]['prediction']
    assert all(v['passed']==0 and v['denominator']==8 for v in scores['paired'])
    positive={(v['key'],1):v['label'] for v in cases if v['kind']=='probe' and v['probe'] is not None}
    assert all(v['passed']==8 for v in measurement.language_scores(cases,positive)['paired'])
    contradictory={key:'松子、铃铛' for key in positive}
    assert all(v['passed']==0 for v in measurement.language_scores(cases,contradictory)['paired'])
    constant={key:'松子' for key in positive}
    assert all(v['passed']==0 for v in measurement.language_scores(cases,constant)['paired'])
    assert measurement.classify('') is None and measurement.classify('松子。松子。')=='松子'
    rows=[]
    from threemind_runtime.codec import ArtifactCodec
    historical=material.read(material.OLD/'structural-diagnostic.json')['rows']
    by={(v['source'],v['seconds']):v for v in historical}
    maximum=0.
    for source in inventory['sources']:
        for seconds in (530,830):
            path=material.OLD/'cases'/source['key']/'checkpoints'/str(seconds)/'state.tmind'
            state=ArtifactCodec.decode(path.read_bytes()).to_dict()
            assert state['dynamics']=='threemind.continuous-memory/2'
            measured=measurement.structure(state,source['seed'])
            reference=by[source['key'],seconds]
            for kind,value in measured['edges'].items():
                old_value=reference['edges'].get(kind,{'count':0,'max_weight':0.})
                assert value['count']==old_value['count']
                error=abs(value['max_weight']-old_value['max_weight']);assert error<1e-12
                maximum=max(maximum,error)
            rows.append({'seed':source['seed'],'condition':source['condition'],'seconds':seconds,**measured})
    retention=measurement.retention_decisions(rows)
    assert retention['weight_advantage_replicated'] and retention['count_advantage_replicated']
    assert not retention['scientific_stop']
    absent=copy.deepcopy(rows)
    for row in absent:
        if row['condition']=='spaced':row['edges']['language-to-language']={'count':0,'max_weight':0.,'weights':[]}
    assert measurement.retention_decisions(absent)['scientific_stop']
    assert measurement.transmission({'initial_metrics':{'transport':{'sent':10.,'discarded':3.}},
        'metrics':{'transport':{'sent':13.,'discarded':4.}}})['passed']==2.
    proof={'passed':True,'created_engines':0,'created_decoders':0,'historical_scored_responses':400,
        'historical_dose_responses':40,'historical_structure_snapshots':20,
        'maximum_structure_error':maximum,'negative_and_positive_fixtures_passed':True,
        'historical_paired_successes':[v['passed'] for v in scores['paired']],
        'measurement_source_sha256':material.sha(Path(measurement.__file__)),
        'historical_analysis_sha256':material.sha(material.OLD/'analysis-v1.json')}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(proof,stream,ensure_ascii=False,sort_keys=True)
    print(json.dumps(proof),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args().output.resolve())
