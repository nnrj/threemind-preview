import copy
import numpy as np
import pytest
from lab.tools.expression_observation import ExpressionObservation, decode_timed
from threemind_transformer.native_readout import NativeProjection


def process(start=0, a=2, i=1):
    return {'start_us':str(start),'end_us':str(start+100),'planned_end_us':str(start+100),
            'trajectory':[{'time_us':str(start+t),'nodes':[{'channel':7,'activation':a,'inhibition':i},
                                                         {'channel':8,'activation':9,'inhibition':8}]}
                          for t in (0,100)]}


def observation(mode='absolute',fields=('activation',)):
    return ExpressionObservation(NativeProjection((7,),(8,),bins=2).to_dict(),mode,fields)


def test_absolute_preserves_existing_features_and_inputs():
    p=process();saved=copy.deepcopy(p)
    result=observation().project(p)
    assert np.allclose(result['values'],NativeProjection((7,),(8,),bins=2).project(p)['values'])
    assert p==saved


def test_signed_response_and_zero_counterfactual():
    obj=observation('paired',('activation','inhibition'))
    p=process(a=1,i=3);b=process(a=2,i=1);saved=copy.deepcopy((p,b))
    values=np.array(obj.project(p,b)['values'])
    assert values.min()<0<values.max()
    assert values.shape==(obj.basis.bins,obj.basis.width)
    assert np.abs(values).sum()==pytest.approx(1)
    assert not obj.project(p,p)['resolvable']
    assert (p,b)==saved


def test_baseline_timing_and_missing_fields_are_rejected():
    with pytest.raises(ValueError):observation('paired').project(process(),process(1))
    with pytest.raises(ValueError):observation('preceding').project(process(),process(1))
    with pytest.raises(ValueError):observation('paired').project(process())
    with pytest.raises(KeyError):
        p=process();del p['trajectory'][0]['nodes'][0]['inhibition']
        observation('paired',('activation','inhibition')).project(p,process())
    assert observation('preceding').project(process(100),process())['contrast_magnitude']==0


def test_timestamped_output_remains_tied_to_source_interval():
    class Reader:
        def decode(self,rows):return [{'text':str(r),'cross_window_cache':False} for r in rows]
    windows=[{'id':'old-window','start_us':'5','end_us':'10'}]
    result=decode_timed(Reader(),[2],windows,queued_at_ns=1)[0]
    assert result['window']==windows[0]
    assert result['queue_seconds']>0
    assert result['output']['text']=='2'
    with pytest.raises(ValueError):decode_timed(Reader(),[1,2],windows*2)
