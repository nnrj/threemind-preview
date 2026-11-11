"""Finite-vocabulary linear transcription of raw local processes.

A research diagnostic, not a general language generator. No centering,
counterfactual subtraction, per-example scaling or semantic channel selection.
Teacher words are the only supervision. Inference takes a process alone.
"""
import json
from pathlib import Path

import numpy as np

from threemind_transformer.graph_expression import GraphExpressionConfig, pack_graphs
from threemind_transformer.local_activity import FIELDS

VERSION = 'threemind.local-word-transcriber/1'


class LocalWordTranscriber:
    def __init__(self, ridge=0.0001):
        if not 0 < ridge <= 1:
            raise ValueError('positive bounded ridge')
        self.ridge = ridge
        self.words = []
        self.keys = []
        self.grid = None
        self.weights = None

    @staticmethod
    def measure(process):
        pack_graphs([process], GraphExpressionConfig(node_fields=FIELDS, use_edges=False), 'cpu')
        if any(frame['edges'] for frame in process['frames']):
            raise ValueError('this reader requires node-only local processes')
        start = int(process['start_us'])
        grid = [int(frame['time_us'])-start for frame in process['frames']]
        values = {(i, node['channel'], j): float(value)
                  for i, frame in enumerate(process['frames']) for node in frame['nodes']
                  for j, value in enumerate(node['values'])}
        return grid, values

    def fit(self, examples):
        if not 2 <= len(examples) <= 128:
            raise ValueError('2..128 teacher examples')
        measured = [self.measure(row['process']) for row in examples]
        self.grid = measured[0][0]
        if any(grid != self.grid for grid, _ in measured):
            raise ValueError('explicitly match relative observation sample times')
        self.words = sorted({row['text'] for row in examples})
        if not 2 <= len(self.words) <= 32 or any(not isinstance(w, str) or not w or len(w) > 64 for w in self.words):
            raise ValueError('bounded literal vocabulary')
        self.keys = sorted({key for _, values in measured for key in values})
        if len(self.keys) > 65536:
            raise ValueError('feature budget')
        x = np.asarray([[1., *(values.get(key, 0.) for key in self.keys)] for _, values in measured])
        y = np.zeros((len(examples), len(self.words)))
        for i, row in enumerate(examples):
            y[i, self.words.index(row['text'])] = 1.
        # Dual ridge: learns weights, does not modify or center the observations.
        self.weights = x.T @ np.linalg.solve(x @ x.T + self.ridge*np.eye(len(x)), y)
        if not np.isfinite(self.weights).all():
            raise ValueError('nonfinite fit')
        return self

    def decode(self, process):
        if self.weights is None:
            raise ValueError('untrained reader')
        grid, values = self.measure(process)
        if grid != self.grid:
            raise ValueError('observation sample times differ')
        x = np.asarray([1., *(values.get(key, 0.) for key in self.keys)])
        scores = x @ self.weights
        known = set(self.keys)
        return {'text': self.words[int(np.argmax(scores))], 'scores': dict(zip(self.words, scores.tolist())),
                'untrained_features': sum(key not in known for key in values),
                'limitation': 'finite vocabulary; scores are not calibrated probabilities'}

    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        np.save(folder/'weights.npy', self.weights, allow_pickle=False)
        (folder/'manifest.json').write_text(json.dumps({'schema': VERSION, 'ridge': self.ridge,
            'words': self.words, 'keys': self.keys, 'grid': self.grid,
            'input_processing': 'raw local fields; no centering or query scaling'}, ensure_ascii=False), encoding='utf-8')

    @classmethod
    def restore(cls, folder):
        folder = Path(folder)
        if (folder/'manifest.json').stat().st_size > 8*2**20 or (folder/'weights.npy').stat().st_size > 32*2**20:
            raise ValueError('checkpoint budget')
        m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if m['schema'] != VERSION or len(m['keys']) > 65536 or not 2 <= len(m['words']) <= 32:
            raise ValueError('checkpoint contract')
        value = cls(m['ridge'])
        value.words, value.keys, value.grid = m['words'], [tuple(k) for k in m['keys']], m['grid']
        value.weights = np.load(folder/'weights.npy', allow_pickle=False)
        if value.weights.shape != (len(value.keys)+1, len(value.words)) or not np.isfinite(value.weights).all():
            raise ValueError('invalid learned weights')
        return value
