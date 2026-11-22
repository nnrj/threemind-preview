"""Read-only temporal/endpoint M5 scoring; historical goals are scored separately."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
from allocation import disk_allocation
from audit_readout import audit
from m5_analyze import summarize_unit

def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

def endpoint_view(result):

    def convert(value):
        if isinstance(value, list):
            return [convert(v) for v in value]
        if not isinstance(value, dict):
            return value
        out = {k: convert(v) for k, v in value.items()}
        for key in ('response', 'port_response', 'features', 'port_features', 'readers_before', 'readers_after'):
            if 'endpoint_' + key in out:
                out[key] = copy.deepcopy(out['endpoint_' + key])
        return out
    return convert(result)

def goals(units):
    out = {}
    for head in ('full', 'ports'):
        for target in ('first_expression', 'causal_attribution', 'continued_reader_gain'):
            count = sum((u['tests'][head][target] for u in units))
            valid = all((u['integrity_valid'] and (target != 'causal_attribution' or u['matching_valid']) for u in units))
            out[head + '-' + target] = {'passed_origins': count, 'n': 8, 'verdict': 'INVALID' if not valid else 'PASS' if count >= 6 else 'FAIL'}
    count = sum((u['representation_gain'] for u in units))
    out['output-port-representation-gain'] = {'passed_origins': count, 'n': 8, 'verdict': 'PASS' if count >= 6 else 'FAIL'}
    return out
