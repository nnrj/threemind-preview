"""Publish reviewed r3 interim texts while the separate /4 host may be active.

Only ordinary authenticated database text/entry APIs are called. No research
original, recorder journal, subject or running host is modified by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    complete = json.loads((work/'computation-complete.json').read_bytes())
    if complete['arms'] != ['2', '3.1']:
        raise ValueError('two completed arms required for this interim edition')
    verified = json.loads((work/'analysis/verified-results.json').read_bytes())
    if not verified['matched_input_sequences']:
        raise ValueError('interim input audit incomplete')
    for arm in ('2', '3.1'):
        receipt = json.loads((work/'replays'/arm/'export.json').read_bytes())
        video = work/receipt['video']
        if hashlib.sha256(video.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError('replay differs from verified receipt: '+arm)
    bodies = {lang: (HERE/f'report.{lang}.md').read_text(encoding='utf-8') for lang in ('zh', 'en')}
    if any('未发布草稿' in body or 'unpublished draft' in body for body in bodies.values()):
        raise ValueError('interim report review is incomplete')
    meta = json.loads((work/'platform.json').read_bytes())
    project = meta['project_id']
    identity = json.loads((work/'.research-records/identity.json').read_bytes())['experiment']
    def rid(key):
        return str(uuid5(UUID(project), 'e67:'+key))
    load_env()
    with OperationsClient.from_environment(source='ai') as client:
        path = {'project': project, 'experiment': identity}
        outputs = {}
        for lang, body in bodies.items():
            outputs[lang] = client.call('records.text', {'path': path, 'body': dict(
                request_id=rid('interim-r3-report:'+lang), identity=rid('interim-r3-report-text:'+lang),
                expected_revision=0, kind='report', title=f'E67 第3版两组阶段报告 / interim two-arm report · {lang}',
                markdown=body)}, request_id=rid('interim-r3-report:'+lang))
        note = client.call('records.text', {'path': path, 'body': dict(
            request_id=rid('interim-r3-note'), identity=rid('interim-r3-note-text'),
            expected_revision=0, kind='note', title='E67 前两组完成时的执行札记',
            markdown=(HERE/'notes.zh.md').read_text(encoding='utf-8'))}, request_id=rid('interim-r3-note'))
        client.call('records.append', {'path': path, 'body': dict(request_id=rid('interim-r3-delivery'),
            kind='correction', original_key='interim-r3-delivery', content=dict(
                completed_arms=['2', '3.1'], continuing_arms=['4-adaptive', '4-legacy'],
                experiment_finalized=False, report_scope='Reviewed interim texts only; four-arm comparison follows.',
                publisher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))},
            request_id=rid('interim-r3-delivery'))
        detail = client.call('records.detail', {'path': path})
        print(json.dumps(dict(experiment=identity, execution_status=detail['execution_status'],
            reports={lang: value['text']['id'] for lang, value in outputs.items()},
            note=note['text']['id'],
            experiment_finalized=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
