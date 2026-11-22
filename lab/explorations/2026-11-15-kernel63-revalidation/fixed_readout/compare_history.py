"""Ancillary read-only comparison; frozen scoring and scientific data stay intact."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study


def compare(work):
    study.frozen_check(work)
    assert study.read(work/'audit.json')['passed']
    old = work.parent/'fixed-readout61-v1'
    a, b = study.read(old/'analysis.json'), study.read(work/'analysis.json')
    fields = ('valid','independent_origins','primary_condition','temporal_goals','endpoint_goals',
              'temporal_units','endpoint_units','old_correction_rounds','scientific_stop')
    count, maximum, differences = 0, 0., []

    def walk(left,right,path):
        nonlocal count,maximum
        if isinstance(left,dict) and isinstance(right,dict):
            assert left.keys() == right.keys(),path
            for k in left: walk(left[k],right[k],path+'/'+k)
        elif isinstance(left,list) and isinstance(right,list):
            assert len(left) == len(right),path
            for i,(x,y) in enumerate(zip(left,right)): walk(x,y,path+'/'+str(i))
        elif type(left) in (int,float) and type(right) in (int,float):
            count += 1
            maximum = max(maximum,abs(left-right))
        elif left != right:
            differences.append({'path':path,'historical':left,'current':right})

    walk({k:a[k] for k in fields},{k:b[k] for k in fields},'')
    result = {'historical_work':str(old),'current_work':str(work),'fields':list(fields),
              'historical_analysis_sha256':study.s.sha(old/'analysis.json'),
              'current_analysis_sha256':study.s.sha(work/'analysis.json'),
              'numeric_fields_checked':count,'maximum_numeric_difference':maximum,
              'categorical_differences':differences,'Core_engines_loaded':0,
              'historical_wall_seconds':a['timing']['wall_seconds'],
              'current_wall_seconds':b['timing']['wall_seconds'],
              'historical_peak_private_bytes':a['resources']['peak_private_bytes'],
              'current_peak_private_bytes':b['resources']['peak_private_bytes']}
    study.s.base.original(work/'historical-comparison.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True)
    compare(parser.parse_args().work.resolve())
