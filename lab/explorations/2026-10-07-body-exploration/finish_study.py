"""Resume completed-case boundaries and the preregistered posture decision branch."""
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent


def module(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    c=module('caregiver');e=c.e;e.TAG='gain01-';e.ACTIVITY_GAIN=.1;s=e.study()
    def run(key,seconds,fn,extension=False):
        result=e.WORK/'cases'/key/'result.json'
        if result.exists():return json.loads(result.read_text(encoding='utf-8'))
        s.guard(True)
        if extension:s.allow_extension()
        remain=s.settings.wall_seconds-s.completed_wall-getattr(s,'failed_wall',0)
        if remain<seconds+60:raise RuntimeError('case boundary: reserve remaining compute')
        return fn()
    try:
        for source in (0,1):
            for group in e.GROUPS:
                run(f'A-gain01-{source}-{group}',400,lambda:e.explore(s,source,group))
                run(f'B-gain01-{source}-{group}',750,lambda:e.teach(s,source,group))
                run(f'V-gain01-{source}-{group}',180,lambda:e.validation(s,source,group))
                run(f'C-gain01-{source}-{group}',40,lambda:e.fit(s,source,group))
                run(f'D-gain01-{source}-{group}-read-{group}-normal',350,lambda:e.evaluate(s,source,group))
            run(f'A-gain01-{source}-guided',520,lambda:c.guided(s,source))
            for group,cut in [('guided',False),('explore',False),('guided',True)]:
                run(f'W-gain01-{source}-{group}-'+('cut' if cut else 'normal'),140,lambda:c.probe(s,source,group,cut))
            for group,cut in [('guided',False),('explore',False),('guided',True)]:
                run(f'W2-gain01-{source}-{group}-'+('cut' if cut else 'normal'),140,lambda:c.probe(s,source,group,cut,True))
        for group,model,mode in [('quiet','explore','normal'),('explore','quiet','normal'),
                                 ('explore','explore','silence'),('explore','explore','rescue'),('explore','explore','empty')]:
            run(f'D-gain01-0-{group}-read-{model}-{mode}',350,lambda:e.evaluate(s,0,group,mode,model))
        p=module('pose_control')
        run('P-fit-0-explore',40,lambda:p.fit(s,0,'explore'),True)
        pose=run('P-test-0-explore',350,lambda:p.evaluate(s,0,'explore'),True)
        base=json.loads((e.WORK/'cases/D-gain01-0-explore-read-explore-normal/result.json').read_text(encoding='utf-8'))
        worthy=any(pose[field]-base[field]>=3 for field in ('eye_enter_and_finish','hand_enter_and_finish'))
        decision={'posture_additional_comparison_triggered':worthy,'criterion':'at least 3/12 more entered-and-finished eye or hand phases; not a revised success threshold'}
        path=e.WORK/'posture-decision.json'
        if not path.exists():e.new_json(path,decision)
        print(json.dumps(decision),flush=True)
        if worthy:
            run('P-fit-1-explore',40,lambda:p.fit(s,1,'explore'),True)
            run('P-test-1-explore',350,lambda:p.evaluate(s,1,'explore'),True)
            for mode in ('silence','rescue'):
                run('P-test-0-explore-'+mode,350,lambda:p.evaluate(s,0,'explore',mode),True)
            # Empty mode never invokes either reader, so its same-world, same-
            # Core zero-command recording is a shared control, not a new sample.
            alias=e.WORK/'posture-shared-control.json'
            if not alias.exists():e.new_json(alias,{'zero_command_case':'D-gain01-0-explore-read-explore-empty',
                'reason':'identical zero-command branch bypasses both readers in the same task/session'})
        print(json.dumps({'status':'bounded continuation complete'}),flush=True)
    except RuntimeError as error:
        print(json.dumps({'status':'stopped; evidence preserved','reason':str(error)}),flush=True)
        raise
    finally:s.db.close()


if __name__=='__main__':main()
