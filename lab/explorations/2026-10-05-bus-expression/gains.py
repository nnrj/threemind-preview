"""Compare effective configurations, not omitted-default serialization fields."""
from common import *
from threemind_kernels.novelty import NoveltyConfig
from threemind_runtime.stimulus_presets import TEXT_INTENSITY_PRESETS

keys=('stp_enabled','depletion_enabled','edge_consolidation_enabled','stp_facilitation_tau_s',
    'stp_recovery_tau_s','context_enabled','fast_enabled','plasticity','inhibition','novelty_mode',
    'local_novelty_gain','novelty_touch_reference','intensity_gain','associative_gain','learning_rate',
    'forgetting_rate','activation_tau','propagation_interval_us','homeostasis_enabled','attention_competition_enabled')
actual=NoveltyConfig(**read_json(OLD/'cases/s223-continued/definition.json')['config']);default=NoveltyConfig()
result={k:{'default':getattr(default,k),'experiment':getattr(actual,k)} for k in keys}
new_json(HERE/'effective-mechanisms.json',{'kernel':'threemind.continuous-memory/2','values':result,'input_presets':TEXT_INTENSITY_PRESETS,
    'scope':'effective fields restored through the configuration class; omitted serialized defaults are not missing mechanisms'})
print(result)
