"""Publish E68 evidence and separately reviewed reports, never rerun simulation."""
import argparse
from pathlib import Path
from experiment import Study,RESOURCE,HERE,read


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('originals','reports'))
    p.add_argument('--work',type=Path,required=True);args=p.parse_args();s=Study(args.work)
    try:
        with s.storage.writer(RESOURCE):
            if not (s.work/'computation-complete.json').exists():raise ValueError('unfinished computation')
            if args.action=='originals':
                # Refer to existing bytes; never upload a duplicate evidence package.
                for root in (s.work/'analysis',s.work/'replays'):
                    for path in sorted(root.rglob('*')):
                        if path.is_file() and '.partial' not in path.name:
                            s.attach(path,'replay' if path.suffix=='.mp4' else 'result')
                for arm in ('2','3.1'):
                    s.attach(s.work/'arms'/arm/'blank-birth.json','protocol')
                s.attach(s.work/'computation-complete.json','result')
                s.sync()
            else:
                for lang in ('zh','en'):
                    path=HERE/f'report.{lang}.md'
                    if not path.exists():raise ValueError('reviewed report missing: '+str(path))
                    s.recorder.text(dict(request_id=s.rid('final-report:'+lang),identity=s.rid('final-report-text:'+lang),
                        expected_revision=0,kind='report',title='E68 连续形色最终报告 / Final report '+lang,
                        markdown=path.read_text(encoding='utf-8')))
                for arm in ('2','3.1'):
                    receipt=read(s.work/'replays'/arm/'export.json')
                    if receipt.get('activity_curves')!=['activation','inhibition','direct','associative']:
                        raise ValueError('required activity curves missing')
                s.recorder.synchronize(strict=True)
                s.recorder.finalize('completed',request_id=s.rid('finalize'))
                s.recorder.synchronize(strict=True)
    finally:s.close()


if __name__=='__main__':main()
