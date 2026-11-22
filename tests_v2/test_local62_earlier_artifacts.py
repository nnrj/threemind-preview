"""Earlier 6.2 definitions retain their checksum and former dynamics."""
import hashlib
import pytest
from threemind_core import StateImage, Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local62 import Local62Config
from threemind_kernels.registry import resolve_kernel
from test_local60 import same


@pytest.mark.parametrize('backend',['reference','native'])
def test_earlier_definition_restores_with_enabled_weight_switches(backend):
    d=resolve_kernel('threemind.continuous-memory/6.2')
    original=d.create(Local62Config(consolidation_mode='stability'),backend=backend)
    original.inject(Stimulus(0,((1,.4),(2,.3))));original.advance_to(100000)
    state=original.capture_state().to_dict()
    for key in ('activation_weight_reinforcement_enabled','inhibition_weight_reinforcement_enabled'):
        state['config'].pop(key);state['definition']['config'].pop(key)
    state['definition_hash']=hashlib.sha256(canonical_bytes(state['definition'])).hexdigest()
    restored=d.create(state=StateImage.from_dict(state),backend=backend)
    same(original.capture_state().to_dict(),restored.capture_state().to_dict())
    original.advance_to(1000000);restored.advance_to(1000000)
    same(original.capture_state().to_dict(),restored.capture_state().to_dict())
    state['config']['inhibition_gain']+=.01
    with pytest.raises(ValueError,match='definition/hash'):
        d.create(state=StateImage.from_dict(state),backend=backend)
