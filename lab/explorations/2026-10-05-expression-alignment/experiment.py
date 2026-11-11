"""E47 paired-copy experiments; no change to kernel dynamics or teaching mapping."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import torch
from lab.tools.service_study import Study,StudyConfig,read_json,new_json,write_gzip,encoded

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/expression-alignment-20261005'
OLD=ROOT/'.work/native-language-20261005'
spec=importlib.util.spec_from_file_location('e46_alignment_helpers',ROOT/'lab/explorations/2026-10-05-native-language/experiment.py')
e46=importlib.util.module_from_spec(spec);spec.loader.exec_module(e46)
SEEDS=e46.SEEDS


def study(prepare=False):
    return Study(StudyConfig('expression-alignment/1','E47 表达延迟与新经历',HERE,WORK,43,
        instance_limit=1600,wall_seconds=21600,storage_soft=6*2**30,storage_hard=10*2**30,
        usage_soft_delta=8,usage_hard_delta=12),prepare=prepare)


def guard(s,force=False):
    s.guard(force)
    if force or not hasattr(s,'extra_seconds'):
        s.extra_seconds=sum(read_json(p).get('wall_seconds',0) for p in (WORK/'timing').glob('*.json'))
    active=time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall+s.extra_seconds+active >= s.settings.wall_seconds:
        raise RuntimeError('aggregate compute budget reached')
    if torch.cuda.is_available() and torch.cuda.memory_allocated()>3*2**30:
        raise RuntimeError('GPU memory budget reached')


def helpers():
    # Input is loaded from the immutable prior artifact before choosing a new
    # destination for newly created probes. No old file is overwritten.
    e46.WORK=OLD
    adapter=e46.inp()
    e46.WORK=WORK
    e46.guard=guard
    return adapter


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=('prepare','calibration'))
    args=parser.parse_args()
    torch.set_num_threads(2)
    s=study(args.operation=='prepare')
    try:
        if args.operation=='prepare':
            for name in ('physical-telemetry.jsonl','projection.json','route-selection.json'):
                shutil.copy2(OLD/name,WORK/name)
            new_json(WORK/'usage.json',{'used_percent':43})
            for name in ('lab/tools/expression_observation.py','lab/tools/native_expression.py',
                         'lab/tools/recorded_background.py','lab/tools/language_teaching_world.py','lab/tools/sensory_calibration.py',
                         'lab/explorations/2026-10-05-native-language/experiment.py',
                         'lab/explorations/2026-10-05-language-calibration/experiment.py',
                         'lab/explorations/2026-10-04-language-development/experiment.py'):
                dest=WORK/'frozen-tools'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
            print({'project':s.project},flush=True)
        else:
            adapter=helpers()
            for seed in SEEDS:
                for condition,seconds in (('normal',326),('continued',532),('continued',592),('reversal',532),
                                           ('reversal',592),('background',532),('background',592)):
                    parent=OLD/'cases'/f's{seed}-{condition}'
                    for modality in ('vision','words'):
                        for item in range(4):
                            for variant,intensity in (((0,.4),(0,.6)) if modality=='vision' else ((8,.4),(10,.6))):
                                e46.probe(s,adapter,parent,seconds,modality,item,variant,intensity,'train')
                        e46.probe(s,adapter,parent,seconds,modality,-1,0,.5,'train')
                    print({'calibrated':parent.name,'seconds':seconds,'cases':s.completed_count},flush=True)
    finally:
        s.db.close()


if __name__=='__main__':main()
