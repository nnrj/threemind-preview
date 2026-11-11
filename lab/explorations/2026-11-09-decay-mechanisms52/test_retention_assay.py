"""Synthetic instrument checks; no samples enter the scientific comparison."""
import pytest
from retention_assay import Assay,TIMES,DOSES,FIELDS,temporal_contrast


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
@pytest.mark.parametrize('relaxation',[True,False])
def test_assay_continuity_and_temporal_observation(curve,relaxation):
    s=Assay(26110991,curve,relaxation,'engineering-instrument')
    taught=s.teach('spaced',False,1)
    assert taught['time_us']==128000000
    saved=s.state();s.measure();assert saved==s.state()
    copy=Assay.restore(saved)
    x=s.first_probe(1);y=copy.first_probe(1)
    assert x==y and s.state()==copy.state()
    assert set(temporal_contrast(x['response']))==set(FIELDS)
    assert len(x['baseline']['raw'])==len(x['response']['raw'])==20
    assert x['response']['start_us']==129000000
    assert len([r for r in s.events if r['role']=='cue-probe'])==1
    assert all(r['end_us']-r['start_us']==1000000 for r in (x['baseline'],x['response']))


def test_dose_matched_spacing_and_familiarization():
    assert len(TIMES['massed'])==len(TIMES['spaced'])==8
    assert TIMES['massed'][-1]==TIMES['spaced'][-1]==127
    assert DOSES['massed']==DOSES['spaced']
    gaps=[b-a for a,b in zip(TIMES['spaced'],TIMES['spaced'][1:])]
    assert gaps==sorted(gaps)
    for familiar in (False,True):
        s=Assay(26110992,'exponential',True,'engineering-familiarity')
        s.teach('weak',familiar,0)
        pre=[r for r in s.events if r['role'] in ('familiarization','matched-neutral')]
        assert len(pre)==12 and all(len(r['channels'])==1 for r in pre)


def test_longer_background_history_preserves_next_response_on_restore():
    s=Assay(26110995,'inverse-logarithmic',False,'engineering-long-background')
    s.teach('weak',False,0)
    s.first_probe(300)
    saved=s.state();restored=Assay.restore(saved)
    assert s.window({'cue':.7})==restored.window({'cue':.7})
    assert s.state()==restored.state()


def test_prompt_omission_controls_are_matched_until_the_final_window():
    values=[]
    for cue in (True,False):
        s=Assay(26110997,'power-law',True,'excluded-prompt-control')
        s.teach('ordinary',False,0)
        result=s.first_probe(1,cue)
        assert len([x for x in s.events if x['role']=='cue-probe'])==int(cue)
        assert s.core.time_us==130000000 and result['cue_present']==cue
        values.append(result)
    assert values[0]['before']==values[1]['before']
    assert values[0]['baseline']==values[1]['baseline']
    assert values[0]['response']['raw']!=values[1]['response']['raw']
