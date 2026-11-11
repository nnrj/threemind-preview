"""Single-worker continuation, leaving publication reserve and preserving failures."""
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent


def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    c=module('caregiver');e=c.e;e.TAG='gain01-';e.ACTIVITY_GAIN=.1;s=e.study()
    def room(seconds,extension=False):
        s.guard(True)
        if extension:s.allow_extension()
        remaining=s.settings.wall_seconds-s.completed_wall-getattr(s,'failed_wall',0)
        if remaining < seconds+120:raise RuntimeError('stop at case boundary to preserve registered compute budget')
    try:
        # The original source-0 batch has to finish first. Never run a second worker.
        for group in e.GROUPS:
            if not (e.WORK/'cases'/f'D-gain01-0-{group}-read-{group}-normal'/'result.json').exists():
                raise RuntimeError('finish source-0 batch before continuation')
        room(500);c.guided(s,0)
        for group,cut in [('guided',False),('explore',False),('guided',True)]:
            room(160);c.probe(s,0,group,cut)
        for group in e.GROUPS:
            room(1500);e.explore(s,1,group);e.teach(s,1,group);e.validation(s,1,group);e.fit(s,1,group);e.evaluate(s,1,group)
        room(500);c.guided(s,1)
        for group,cut in [('guided',False),('explore',False),('guided',True)]:
            room(160);c.probe(s,1,group,cut)
        # The same fixed reader separates Core history from separately trained heads.
        for group,model,mode in [('quiet','explore','normal'),('explore','quiet','normal'),
                                 ('explore','explore','silence'),('explore','explore','rescue'),('explore','explore','empty')]:
            room(350);e.evaluate(s,0,group,mode,model)
        # Optional external-actuation diagnostic only after primary and withdrawal comparisons.
        room(400,extension=True)
        p=module('pose_control');p.fit(s,0,'explore');p.evaluate(s,0,'explore')
        print(json.dumps({'status':'bounded study completed'}))
    except RuntimeError as error:
        print(json.dumps({'status':'stopped at registered bound or recorded failure','reason':str(error)}),flush=True)
        raise
    finally:s.db.close()


if __name__=='__main__':main()
