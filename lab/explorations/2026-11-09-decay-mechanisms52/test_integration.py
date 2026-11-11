"""Public /5.2 interface checks; use the isolated staged package until promotion."""
from dataclasses import asdict,fields
import copy
import pytest
from threemind_core import Stimulus
from threemind_kernels.local52 import Local52Config,Local52Engine,KERNEL_ID
from threemind_kernels.registry import resolve_kernel,creation_kernel,DEFAULT_KERNEL
from threemind_runtime.host import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth
from threemind_lab.configuration import catalogue,default_spec,validate_configuration


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
@pytest.mark.parametrize('relaxation',[True,False])
@pytest.mark.parametrize('fmt',['json','tmind'])
def test_complete_codec_next_event(curve,relaxation,fmt):
    cfg=Local52Config(decay_curve=curve,retention_relaxation_enabled=relaxation)
    a=create_engine(cfg,backend='reference')
    assert type(a) is Local52Engine
    a.inject(Stimulus(0,((10,.8),(20,.6))));a.advance_to(137001)
    old=a.capture_state();raw=ArtifactCodec.encode(old,fmt);new=ArtifactCodec.decode(raw)
    assert old.payload==new.payload==a.capture_state().payload
    b=create_engine(state=new,backend='reference')
    for e in (a,b):
        e.inject(Stimulus(200000,((10,.5),(21,.7))));e.advance_to(1000000)
    assert a.capture_state().payload==b.capture_state().payload


def test_version_routing_and_unsupported_inheritance():
    from threemind_lab.execution import select_execution
    d=resolve_kernel(KERNEL_ID)
    assert d.backends==('reference',) and DEFAULT_KERNEL=='threemind.continuous-memory/3'
    assert select_execution(KERNEL_ID,default='native')=={'backend':'reference'}
    with pytest.raises(ValueError,match='no automatic fallback'):
        select_execution(KERNEL_ID,{'backend':'native'})
    assert creation_kernel(config=Local52Config()).kernel_id==KERNEL_ID
    with pytest.raises(ValueError,match='no automatic fallback'):d.create(backend='native')
    image=d.create(backend='reference').capture_state()
    with pytest.raises(ValueError,match='contribution ages'):birth(image)
    with pytest.raises(ValueError,match='identity'):resolve_kernel('threemind.continuous-memory/5.1').create(state=image,backend='reference')


def test_version_owned_configuration_fields_and_immutability():
    cat=catalogue(KERNEL_ID)
    fs={x['path']:x for x in cat['fields'] if x['path'].startswith('config.')}
    retired={'propagation_limit','edge_adaptation_limit','homeostasis_enabled','target_total_activation',
             'spatial_competition_rate','attention_competition_enabled','attention_budget',
             'edge_birth_policy','association_window_us','step_us'}
    assert set(fs)=={'config.'+f.name for f in fields(Local52Config) if f.name not in retired}
    assert fs['config.decay_curve']['immutable']
    assert not fs['config.retention_relaxation_enabled']['immutable']
    assert '时间尺度' in fs['config.memory_half_life_min_s']['label']
    assert 'config.decay_curve' in cat['kernel_immutable'][KERNEL_ID]
    old=default_spec(KERNEL_ID)
    assert validate_configuration(old)['valid']
    new=copy.deepcopy(old);new['config']['decay_curve']='power-law'
    assert validate_configuration(new)['valid']
    assert not validate_configuration(new,current=old)['valid']
    new=copy.deepcopy(old);new['config']['retention_relaxation_enabled']=False
    assert validate_configuration(new,current=old)['valid']
    assert catalogue('threemind.continuous-memory/5.1')['defaults']['config']==asdict(resolve_kernel('threemind.continuous-memory/5.1').configuration())
