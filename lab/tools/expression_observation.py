"""External, versioned observation contrasts and timestamped decoding.

Only dictionaries/arrays enter this module; no engine, mutation or semantic routing.
The paired baseline is a research counterfactual, not an input available to a robot.
"""
from dataclasses import dataclass, asdict
import time

import numpy as np
from threemind_transformer.development import TrajectoryBasis
from threemind_transformer.native_readout import NativeProjection


@dataclass(frozen=True)
class ExpressionObservation:
    projection: dict
    mode: str = 'absolute'
    fields: tuple = ('activation',)
    schema: str = 'threemind.expression-observation/1'

    def __post_init__(self):
        object.__setattr__(self, 'fields', tuple(self.fields))
        if self.schema != 'threemind.expression-observation/1' or self.mode not in ('absolute','paired','preceding'):
            raise ValueError('unsupported observation protocol')
        if self.fields not in (('activation',), ('activation','inhibition')):
            raise ValueError('unsupported observation fields')
        NativeProjection(**self.projection)

    @property
    def basis(self):
        native = NativeProjection(**self.projection).basis
        if len(self.fields) == 1:
            return native
        # Ordinal columns of an explicitly recorded external feature layout,
        # not receptor identities passed back into Core.
        return TrajectoryBasis(tuple(range(native.width * len(self.fields)-native.residual_buckets)),
                               native.bins, native.residual_buckets)

    def raw(self, process):
        native = NativeProjection(**self.projection)
        excluded = set(native.excluded_channels)
        arrays = []; unknown = set()
        for field in self.fields:
            scoped = {key: process[key] for key in ('start_us','end_us','planned_end_us')}
            scoped['trajectory'] = [{'time_us': frame['time_us'], 'nodes': [
                {'channel': node['channel'], 'activation': node[field]}
                for node in frame['nodes'] if int(node['channel']) not in excluded
            ]} for frame in process['trajectory']]
            result = native.basis.project(scoped)
            arrays.append(np.asarray(result['values'], dtype=np.float64))
            unknown.update(result['unknown_channels'])
        return np.concatenate(arrays, axis=1), sorted(unknown)

    def project(self, process, baseline=None):
        values, unknown = self.raw(process)
        raw_magnitude = float(np.abs(values).sum())
        if self.mode != 'absolute':
            if baseline is None:
                raise ValueError('declared baseline is required')
            if self.mode == 'paired':
                if any(int(process[key]) != int(baseline[key]) for key in ('start_us','end_us','planned_end_us')):
                    raise ValueError('paired baseline must cover the same simulated interval')
            elif int(baseline['end_us']) > int(process['start_us']):
                raise ValueError('preceding baseline must not include the future')
            base, others = self.raw(baseline)
            if self.mode == 'preceding':
                base = base.mean(axis=0, keepdims=True)
            values = values-base
            unknown = sorted(set(unknown) | set(others))
        elif baseline is not None:
            raise ValueError('absolute observation does not use a baseline')
        total = float(np.abs(values).sum())
        floor = NativeProjection(**self.projection).minimum_magnitude
        values = values/total if total >= floor else np.zeros_like(values)
        return {'schema': self.schema, 'values': values.astype(np.float32).tolist(),
                'raw_magnitude': raw_magnitude, 'contrast_magnitude': total,
                'resolvable': total >= floor, 'unknown_channels': unknown,
                'mode': self.mode, 'fields': self.fields,
                'start_us': str(process['start_us']), 'end_us': str(process['end_us'])}

    def to_dict(self):
        return asdict(self)


def decode_timed(model, values, windows, *, queued_at_ns=None):
    """Attach result to the sampled interval, never to current simulation time."""
    if len(values) != len(windows) or not len(windows):
        raise ValueError('one window identity per feature row required')
    identities = [row['id'] for row in windows]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate window IDs in batch')
    for row in windows:
        if int(row['end_us']) <= int(row['start_us']):
            raise ValueError('positive sampled interval required')
    started = time.time_ns()
    queued = started if queued_at_ns is None else int(queued_at_ns)
    if queued > started:
        raise ValueError('queue timestamp lies in the future')
    tick = time.perf_counter()
    generated = model.decode(values)
    elapsed = time.perf_counter()-tick
    finished = time.time_ns()
    if len(generated) != len(windows):
        raise ValueError('decoder returned the wrong number of rows')
    return [{'schema':'threemind.timed-expression/1','window':dict(window),'output':output,
             'queued_at_ns':str(queued),'started_at_ns':str(started),'finished_at_ns':str(finished),
             'queue_seconds':(started-queued)/1e9,'batch_decode_seconds':elapsed,
             'batch_size':len(windows),'time_meaning':'sampled_simulation_interval_not_display_time'}
            for window,output in zip(windows,generated,strict=True)]


def main():
    import argparse
    import json
    from pathlib import Path
    from lab.tools.native_expression import FeatureCalibration
    from threemind_transformer.development_model import load
    import torch

    parser=argparse.ArgumentParser(description='Read-only process contrasts or timestamped frozen expression')
    parser.add_argument('operation',choices=('project','decode'))
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True,help='JSONL with id, process and optional baseline')
    parser.add_argument('--output',type=Path,required=True,help='new output, never overwritten')
    parser.add_argument('--device',choices=('auto','cpu','cuda'),default='cpu')
    args=parser.parse_args()
    if args.input.stat().st_size > 256*2**20:
        raise ValueError('input exceeds256MiB; split into bounded files')
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    observation=ExpressionObservation(**manifest['observation'])
    rows=[json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not 1 <= len(rows) <= 16384:
        raise ValueError('bounded nonempty input required')
    model=None
    if args.operation=='decode':
        device='cuda' if args.device in ('auto','cuda') and torch.cuda.is_available() else 'cpu'
        checkpoint=args.manifest.parent/manifest['checkpoint']
        model,_=load(checkpoint,device)
        if model.basis != observation.basis:
            raise ValueError('model observation basis mismatch')
        calibration=FeatureCalibration(**manifest['feature_calibration'])
    with args.output.open('x',encoding='utf-8') as stream:
        for start in range(0,len(rows),16):
            batch=rows[start:start+16]
            features=[observation.project(row['process'],row.get('baseline')) for row in batch]
            if model:
                windows=[{'id':row['id'],'start_us':row['process']['start_us'],'end_us':row['process']['end_us']} for row in batch]
                outputs=decode_timed(model,calibration.transform([f['values'] for f in features]),windows)
                outputs=[r|{'device':device,'contrast_magnitude':f['contrast_magnitude']} for r,f in zip(outputs,features,strict=True)]
            else:
                outputs=[{'id':row['id']}|feature for row,feature in zip(batch,features,strict=True)]
            for row in outputs:
                stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
