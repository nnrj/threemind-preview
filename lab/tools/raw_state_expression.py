"""Read-only raw process features. No contrast, sample scaling or word labels.

Node identity is an anonymous receptor channel, never a semantic reverse map.
Sampling is explicit: callers retain the full source recording alongside features.
"""
from dataclasses import asdict, dataclass
import numpy as np
from threemind_transformer.development import TrajectoryBasis


@dataclass(frozen=True)
class RawStateProjection:
    channels: tuple
    fields: tuple = ('activation', 'inhibition')
    samples: int = 17
    excluded_channels: tuple = ()
    schema: str = 'threemind.raw-state-expression/1'

    def __post_init__(self):
        for name in ('channels', 'fields', 'excluded_channels'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.schema != 'threemind.raw-state-expression/1' or not 2 <= self.samples <= 128:
            raise ValueError('unsupported raw projection')
        if not self.channels or len(set(self.channels)) != len(self.channels):
            raise ValueError('unique anonymous channels required')
        if set(self.channels) & set(self.excluded_channels):
            raise ValueError('included and excluded channels overlap')
        allowed = {'activation', 'inhibition', 'trace', 'support', 'stability',
                   'local_plasticity', 'direct', 'associative', 'generated_inhibition',
                   'pending_inhibition', 'touches', 'touch_age_s'}
        if not self.fields or len(set(self.fields)) != len(self.fields) or set(self.fields)-allowed:
            raise ValueError('explicit supported dynamical fields required')

    @property
    def basis(self):
        # 1 presence column and raw field values for every declared channel.
        width = len(self.channels)*(len(self.fields)+1)
        return TrajectoryBasis(tuple(range(width-1)), self.samples, 1)

    def project(self, process):
        frames = process['trajectory']
        times = [int(f['time_us']) for f in frames]
        if not times or any(a>b for a,b in zip(times,times[1:])):
            raise ValueError('ordered nonempty raw process required')
        start, end = int(process['start_us']), int(process['end_us'])
        if times[0] != start or times[-1] != end or end < start:
            raise ValueError('recording bounds do not match trajectory')
        # Nearest recorded samples, no averaging/interpolation or future beyond
        # the declared window. Exact source times are exposed in the result.
        indices = np.rint(np.linspace(0,len(frames)-1,self.samples)).astype(int)
        index = {int(c):i for i,c in enumerate(self.channels)}
        excluded = set(map(int,self.excluded_channels))
        values = np.zeros((self.samples,len(self.channels),len(self.fields)+1),dtype=np.float32)
        for slot, position in enumerate(indices):
            frame = frames[int(position)]
            for node in frame['nodes']:
                channel = int(node['channel'])
                if channel in excluded:continue
                if channel not in index:
                    raise ValueError(f'unknown channel {channel}; extend declared layout, never drop silently')
                row = values[slot,index[channel]];row[0]=1
                for col,field in enumerate(self.fields,1):
                    if field == 'touch_age_s':
                        value = (int(frame['time_us'])-int(node['last_touch_us']))/1e6
                    else:
                        value = node[field]  # Missing evidence is not a measured zero.
                    row[col] = float(value)
        if not np.isfinite(values).all():raise ValueError('nonfinite state feature')
        return {'schema':self.schema,'values':values.reshape(self.samples,-1).tolist(),
                'sample_times_us':[str(times[int(i)]) for i in indices],
                'normalization':'none','baseline_subtraction':False,
                'start_us':str(start),'end_us':str(end)}

    def to_dict(self):return asdict(self)


def ridge_fit(rows, regularization=1.0):
    """Fixed raw-unit linear diagnostic; intercept is learned, not preprocessing.

    Dual ridge avoids a quadratic allocation in the number of state features.
    Never interprets classification as independent proof of reasoning.
    """
    if not rows or any(r['split'] != 'train' for r in rows):
        raise ValueError('training partition only')
    labels = sorted({r['target'] for r in rows})
    x = np.asarray([r['values'] for r in rows],dtype=np.float64).reshape(len(rows),-1)
    x = np.column_stack([x,np.ones(len(x))])
    y = np.eye(len(labels))[[labels.index(r['target']) for r in rows]]
    coefficients = np.linalg.solve(x@x.T+regularization*np.eye(len(x)),y)
    return {'labels':labels,'training':x,'coefficients':coefficients}


def ridge_predict(model,values):
    x=np.asarray(values,dtype=np.float64).reshape(len(values),-1)
    scores=np.column_stack([x,np.ones(len(x))])@model['training'].T@model['coefficients']
    return [model['labels'][int(i)] for i in scores.argmax(axis=1)]


@dataclass(frozen=True)
class RawGraphBasis:
    width: int
    bins: int = 5
    schema: str = 'threemind.raw-graph-basis/1'

    def __post_init__(self):
        if self.schema!='threemind.raw-graph-basis/1' or not 1<=self.width<=262144 or self.bins!=5:
            raise ValueError('bounded graph layout required')

    def to_dict(self):return asdict(self)


def load_graph_expression(path,device='cpu'):
    import json
    from safetensors import safe_open
    from safetensors.torch import load_file
    from threemind_transformer.development_model import TemporalLanguage
    with safe_open(path,framework='pt',device='cpu') as f:meta=json.loads(f.metadata()['threemind'])
    if meta['schema']!='threemind.temporal-language/1':raise ValueError('invalid expression checkpoint')
    basis=RawGraphBasis(**meta['basis'])
    model=TemporalLanguage(basis,meta['seed'],meta['width'],meta['layers'])
    model.load_state_dict(load_file(path),strict=True)
    return model.to(device).eval(),meta


@dataclass(frozen=True)
class RawGraphStateProjection:
    """Whitelisted full-node/directed-edge state, in raw units.

    A presence flag separates an absent operator from an explicitly stored zero.
    Operator ages preserve lazy-update meaning without guessing recovered values.
    No external pending input, configuration, semantic name or absolute clock.
    """
    channels: tuple
    graph: bool = True
    schema: str = 'threemind.raw-graph-state-expression/1'

    NODE_FIELDS=('activation','inhibition','trace','support','stability','local_plasticity',
                 'direct','associative','generated_inhibition','pending_inhibition','touches')
    EDGE_FIELDS=('weight','stability','eligibility','touches')

    def __post_init__(self):
        object.__setattr__(self,'channels',tuple(self.channels))
        if self.schema!='threemind.raw-graph-state-expression/1' or not self.channels or len(set(self.channels))!=len(self.channels):
            raise ValueError('invalid graph-state projection')

    @property
    def width(self):
        n=len(self.channels)
        return n*(len(self.NODE_FIELDS)+3)+(n*n*15 if self.graph else 0)

    @property
    def basis(self):return RawGraphBasis(self.width)

    def project(self,process):
        states=process['states']
        if len(states)!=5:raise ValueError('five declared complete state samples required')
        times=[int(s['time_us']) for s in states]
        if any(a>b for a,b in zip(times,times[1:])):raise ValueError('state samples must follow time order')
        lookup={int(c):i for i,c in enumerate(self.channels)};n=len(lookup);rows=[]
        for state in states:
            when=int(state['time_us']);node_values=np.zeros((n,len(self.NODE_FIELDS)+3),dtype=np.float32)
            nodes={int(row['id']):row for row in state['nodes']}
            for node in nodes.values():
                channel=int(node['channel'])
                if channel not in lookup:raise ValueError('unregistered state channel')
                node_values[lookup[channel]]=[1,*[float(node[f]) for f in self.NODE_FIELDS],
                    (when-int(node['birth_us']))/1e6,(when-int(node['last_touch_us']))/1e6]
            parts=[node_values.ravel()]
            if self.graph:
                edges=np.zeros((n,n,15),dtype=np.float32)
                def position(row):return lookup[int(nodes[int(row['source'])]['channel'])],lookup[int(nodes[int(row['target'])]['channel'])]
                for edge in state['edges']:
                    i,j=position(edge)
                    edges[i,j,:7]=[1,*[float(edge[f]) for f in self.EDGE_FIELDS],
                        (when-int(edge['birth_us']))/1e6,(when-int(edge['last_touch_us']))/1e6]
                for row in state['operator_state']['short_term']:
                    i,j=position(row);v=row['state']
                    edges[i,j,7:12]=[1,float(v['available']),float(v['active']),float(v['utilization']),
                                     (when-int(v['time_us']))/1e6]
                for row in state['operator_state']['fast']:
                    i,j=position(row);v=row['state']
                    edges[i,j,12:15]=[1,float(v['value']),(when-int(v['time_us']))/1e6]
                parts.append(edges.ravel())
            rows.append(np.concatenate(parts))
        values=np.stack(rows)
        if not np.isfinite(values).all():raise ValueError('nonfinite graph-state value')
        return values

    def to_dict(self):return asdict(self)


def main():
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Project raw anonymous state processes without subtraction or normalization')
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,help='optional frozen raw-expression decoder; no dialogue cache')
    parser.add_argument('--device',choices=('cpu','cuda','auto'),default='cpu')
    args=parser.parse_args()
    if args.input.stat().st_size>256*2**20:raise ValueError('split inputs above256MiB')
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    graph=manifest.get('schema')=='threemind.raw-graph-state-expression/1'
    spec=RawGraphStateProjection(**manifest) if graph else RawStateProjection(**manifest)
    model=None
    if args.checkpoint:
        import torch
        from threemind_transformer.development_model import load
        device='cuda' if args.device in ('cuda','auto') and torch.cuda.is_available() else 'cpu'
        model,_=(load_graph_expression if graph else load)(args.checkpoint,device)
        if model.basis!=spec.basis:raise ValueError('checkpoint feature layout mismatch')
    with args.input.open(encoding='utf-8') as source,args.output.open('x',encoding='utf-8') as dest:
        for line in source:
            if line.strip():
                item=json.loads(line)
                result=({'schema':spec.schema,'values':spec.project(item['process']).tolist(),
                         'sample_times_us':[str(s['time_us']) for s in item['process']['states']],
                         'normalization':'none','baseline_subtraction':False} if graph else spec.project(item['process']))
                if model:
                    result={'schema':spec.schema,'output':model.decode(np.asarray([result['values']],dtype=np.float32))[0],
                            'normalization':'none','baseline_subtraction':False,'device':device,
                            'start_us':item['process']['start_us'],'end_us':item['process']['end_us']}
                dest.write(json.dumps({'id':item['id'],**result},ensure_ascii=False,allow_nan=False)+'\n')


if __name__=='__main__':main()
