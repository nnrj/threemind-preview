"""Recompute historical E15 scores without creating or advancing an individual."""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_original as mat
import measurement_original as m
from threemind_runtime.adapters import channel_id


def check():
    original=mat.SOURCES['main'][0]/'cases'
    @lru_cache(maxsize=4)
    def rows(key):
        with gzip.open(original/key/'behavior.json.gz','rt',encoding='utf-8') as stream:
            return json.load(stream)['rows']
    def channels(seed):
        return {name:channel_id(seed,'ring-sensory-v1',index)
                for name,index in zip('ABCD',(0,1,4,5))}
    result=m.measure(rows,channels)
    assert result['decision']['meets_all']
    assert result['exact_shams']==result['exact_restored_trajectories']==16
    assert result['exact_first_stage_pairs']==8
    assert result['maximum_decimal_motor_error']<1e-12
    proof=m.arithmetic_check()
    proof.update(historical_decision=result['decision'],
        historical_exact_shams=result['exact_shams'],
        historical_exact_restores=result['exact_restored_trajectories'],
        historical_exact_first_stage_pairs=result['exact_first_stage_pairs'],
        maximum_decimal_error=result['maximum_decimal_motor_error'],
        measurement_source_sha256=mat.sha(Path(m.__file__)),
        rows={name:len(result[name]) for name in
              ('local','sequence','environment','memory','retention_extension','texture')})
    return proof


if __name__=='__main__':
    print(json.dumps(check()))
