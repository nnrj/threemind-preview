"""E33: the E32 physical worlds with mutual predation disabled."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_community import CommunityOcean,run
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/ocean-no-predation-20261003'
E32=ROOT/'.work/ocean-community-20261003'


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-no-predation/1','E33 禁止吞食：意识与随机驱动',HERE,WORK,usage,
        instance_limit=4,wall_seconds=21600,storage_soft=4*2**30,storage_hard=8*2**30,
        usage_soft_delta=6,usage_hard_delta=8),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('fresh account reading required')
    # Recover an interrupted registration in its original project; never
    # duplicate a study or overwrite completed simulation evidence.
    s=study(not (WORK/'platform.json').exists(),usage)
    try:
        for lang in ('zh','en'):
            source=HERE/f'design.{lang}.md'
            s.note(f'design:{lang}',f'执行登记 / Study registration {lang}',source.read_text(encoding='utf-8'))
            frozen=WORK/f'design-frozen.{lang}.md'
            if not frozen.exists():shutil.copy2(source,frozen)
        for name in s.implementation['source_files']:
            target=WORK/'frozen-sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(ROOT/name,target)
        if not (WORK/'usage.json').exists():
            write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            target=WORK/'sources'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
        for g in (0,1):
            for mode in ('core','random'):
                key=f'g{g}-{mode}';p=read_json(E32/'protocols'/f'{key}.json')
                reference=WORK/'reference-protocols'/f'{key}.json';target=WORK/'protocols'/f'{key}.json'
                if not reference.exists():write_json(reference,p)
                p['predation']=False
                if not target.exists():write_json(target,p)
        print(json.dumps({'project':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def batch():
    s=study()
    try:
        for group in (0,1):
            for mode in ('core','random'):
                key=f'g{group}-{mode}';out=WORK/'cases'/key
                if (out/'result.json').exists():
                    if read_json(out/'result.json')['status'] not in ('horizon_paused','physical_extinction'):
                        raise RuntimeError('partial case retained: '+key)
                    continue
                if out.exists():raise RuntimeError('partial case retained: '+key)
                s.allow_extension()
                class Clock:pass
                clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
                try:
                    world=CommunityOcean(read_json(WORK/'protocols'/f'{key}.json'))
                    result=run(world,out,120,guard=s.guard)
                finally:s.active_case=None;s.completed_count=None
                print(json.dumps({'complete':key,'status':result['status'],'wall_seconds':result['wall_seconds'],
                    'food':sum(b['grains'] for b in result['members']),'captures':result['totals']['predations'],
                    'alive':sum(b['physical'] for b in result['members'])}),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','batch'))
    p.add_argument('--usage',type=int);a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch()
