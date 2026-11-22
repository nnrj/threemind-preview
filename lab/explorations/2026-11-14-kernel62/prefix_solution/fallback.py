"""Preregistered fallback: separate routing and effective/base inhibitory weights.

Imported after study.py has loaded the historical research helpers. This is a
new research implementation; no historical state or production code is edited.
"""
from dataclasses import dataclass
import research_precheck as old

KERNEL_ID='threemind.research-prefix-solution62-routing/1'
STATE_SCHEMA='threemind.research-prefix-solution62-routing-state/1'

@dataclass(frozen=True,slots=True)
class Config(old.ResearchConfig):
    research_inhibitory_route:str='incident'
    research_inhibitory_weight:str='base'

    def __post_init__(self):
        old.ResearchConfig.__post_init__(self)
        if self.research_inhibitory_route not in ('incident','outgoing'):raise ValueError('route')
        if self.research_inhibitory_weight not in ('base','effective'):raise ValueError('weight')


def definition(config):
    return {'schema':'threemind.kernel-definition/1','kernel_id':KERNEL_ID,
        'state_schema':STATE_SCHEMA,'hypothesis_id':'r51t11/inhibitory-routing',
        'operators':[{'id':'r51t11/inhibitory-route-and-weight','phase':'emission'}],
        'config':config.to_dict()}


class Engine(old.ResearchEngine):
    dynamics=KERNEL_ID
    state_schema=STATE_SCHEMA
    config_type=Config
    definition=staticmethod(definition)

    def _old_inhibition(self,n):
        c=self.config
        if c.research_inhibitory_route=='incident' and c.research_inhibitory_weight=='base':
            return old.ResearchEngine._old_inhibition(self,n)
        if c.inhibition:n.inhibition=self._soft(n.inhibition+n.generated_inhibition)
        n.generated_inhibition=0.0
        transfer=n.inhibition*min(1.0,c.inhibition_diffusion_rate*c.propagation_interval_us/1e6)
        weights={}
        keys=self.incident.get(n.id,()) if c.research_inhibitory_route=='incident' else self.outgoing.get(n.id,())
        if c.inhibition and transfer>=c.inhibition_propagation_min:
            for key in sorted(keys):
                if key in self.silenced_edges or self.edges[key].sleeping:continue
                e=self._settle_edge(key);value=e.weight
                if c.research_inhibitory_weight=='effective' and c.fast_enabled:
                    fast=(old.FastTrace(**(e.fast|{'time_us':int(e.fast['time_us'])})) if e.fast
                          else old.FastTrace(time_us=int(e.birth_us)))
                    value=min(1.0,value+c.fast_gain*fast.projected(self.time_us,self._fast_config))
                target=e.target if e.source==n.id else e.source
                weights[target]=max(weights.get(target,0.0),value)
        total=sum(weights.values())
        if c.inhibition and total>0 and transfer>=c.inhibition_propagation_min:
            transfer=self._expense(n,transfer,c.energy_inhibition_cost,'inhibition')
            if transfer>=c.inhibition_propagation_min:
                n.inhibition-=transfer
                for target,value in sorted(weights.items()):
                    self._emission_inhibitors[target]=self._emission_inhibitors.get(target,0.0)+transfer*value/total


def factory(previous):
    def create(config=None,state=None,backend='reference'):
        if state is not None and state.to_dict()['dynamics']==KERNEL_ID:return Engine(state=state)
        if config is not None and 'research_inhibitory_route' in config:return Engine(Config(**config))
        return previous(config=config,state=state,backend=backend)
    return create
