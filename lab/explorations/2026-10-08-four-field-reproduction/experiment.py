"""Blank-start reproduction using actual E56 functions, isolated evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import Study,StudyConfig,read_json,new_json,encoded

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/four-field-reproduction-20261008'
OLD=ROOT/'lab/explorations/2026-10-06-vision-correction'


def reference_modules():
    spec=importlib.util.spec_from_file_location('e56_reproduction',OLD/'experiment.py')
    e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
    e.WORK=WORK;e.previous.WORK=WORK
    # shared.py explicitly imports its companion experiment module.
    original=sys.modules.get('experiment');sys.modules['experiment']=e
    try:
        spec=importlib.util.spec_from_file_location('e56_shared_reproduction',OLD/'shared.py')
        h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    finally:
        if original is None:sys.modules.pop('experiment',None)
        else:sys.modules['experiment']=original
    h.WORK=WORK
    parent=e.Classroom
    expected=read_json(ROOT/'.work/vision-correction-20261006/cases/r4-teach/protocol.json')['kernel_config']
    class VerifiedBlank(parent):
        def __init__(self,*args,**kwargs):
            if read_json(WORK/'instances.json')['created']>=160:raise RuntimeError('creation budget')
            super().__init__(*args,**kwargs)
            if kwargs.get('state') is None and self.engine.config.to_dict()!=expected:
                raise RuntimeError('birth configuration differs from preserved E56; do not silently adapt')
    e.Classroom=h.Classroom=VerifiedBlank
    return e,h


class BoundedStudy(Study):
    def guard(self,force=False):
        super().guard(force)
        failed=sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                   if not (p.parent/'result.json').exists())
        active=time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+failed+active>3600:raise RuntimeError('aggregate reproduction time budget')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u=urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port!=5433 or u.path!='/threemind':raise ValueError('local DB only')
    return BoundedStudy(StudyConfig('four-field-reproduction/1','E64 从空白复现四视场指认',HERE,WORK,18,
        instance_limit=160,wall_seconds=3600,storage_soft=2**30,storage_hard=2*2**30,
        usage_soft_delta=6,usage_hard_delta=6),prepare=prepare)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare','run'))
    p.add_argument('--usage',type=int,help='Actual account reading, required for prepare')
    a=p.parse_args()
    if a.command=='prepare' and a.usage is None:p.error('actual account usage required')
    s=study(a.command=='prepare')
    try:
        if a.command=='prepare':
            new_json(WORK/'instances.json',{'created':0});new_json(WORK/'usage.json',{'used_percent':a.usage})
            files=[OLD/'experiment.py',OLD/'shared.py',OLD/'confirmation-tasks.json',
                ROOT/'lab/explorations/2026-10-06-grounded-reviews/experiment.py',
                *[ROOT/'lab/tools'/n for n in ('classroom_eye.py','grounded_classroom.py','shape_color_world.py','spatial_choice.py','activity_controller.py')]]
            manifest={}
            for f in files:
                target=WORK/'reference-source'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(f,target);manifest[f.relative_to(ROOT).as_posix()]=hashlib.sha256(f.read_bytes()).hexdigest()
            new_json(WORK/'reference-source/manifest.json',manifest);s.guard(True)
            print(json.dumps({'project_id':s.project}));return
        e,h=reference_modules()
        steps=[('r4-teach',lambda:e.teach(s,4)),
            ('r4-teach-calibration',lambda:e.collect(s,4,'calibration')),
            ('r4-teach-fit',lambda:e.fit(s,4)),
            ('r4-teach-practice-normal',lambda:e.evaluate(s,4,split='practice')),
            ('r4-exposure',lambda:e.correct(s,4,False)),
            ('r4-exposure-practice',lambda:e.collect(s,4,'practice','exposure')),
            ('r4-exposure-fit',lambda:e.fit(s,4,'exposure')),
            ('r4-exposure-test-normal',lambda:e.evaluate(s,4,'exposure')),
            ('r4-exposure-shared-fit',lambda:h.fit(s,4,'exposure')),
            ('r4-exposure-shared-confirmation-normal',lambda:h.test(s,4,'exposure','normal'))]
        for key,fn in steps:
            folder=WORK/'cases'/key
            if (folder/'result.json').exists():continue
            if folder.exists():raise RuntimeError('preserve partial case '+key)
            s.allow_extension();start=time.monotonic()
            try:fn()
            except Exception as error:
                if folder.exists():new_json(folder/'stopped.json',dict(error=str(error),wall_seconds=time.monotonic()-start))
                raise
    finally:s.db.close()


if __name__=='__main__':
    raise SystemExit('Unexecuted, superseded draft. Current authorized E64 is 2026-10-08-centered-restart; do not start an alternative subject.')
