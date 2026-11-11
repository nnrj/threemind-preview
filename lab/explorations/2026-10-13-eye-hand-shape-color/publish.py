"""Publish existing E69 originals and reviewed reports; never run a subject."""
import argparse
from pathlib import Path

from journal import HERE, RESOURCE, ResearchStudy, read, sha

from threemind_lab.storage_files import atomic_json


def publish(study, action):
    work = study.work
    if not (work / 'computation-complete.json').exists():
        raise ValueError('unfinished computation; do not finalize or recreate a subject')
    if list(work.glob('subject/in-flight.json')) or list(work.glob('subjects/*/in-flight.json')) or list(work.glob('arms/*/in-flight.json')):
        raise ValueError('uncommitted experience remains')
    if action == 'originals':
        from pipeline import validate_completed_step
        for step, receipt in (('computation', 'computation-complete.json'),
                              ('analysis', 'analysis/verified-results.json'), ('video', 'replays/export.json')):
            if not (work / receipt).exists():
                raise ValueError('original publication requires completed ' + step)
            validate_completed_step(work, step)
        # Immutable originals are linked, not duplicated into database attachments.
        excluded = {'.research-records', 'source-reference'}
        volatile = {'latest.json', 'progress.json', 'pipeline-status.json', 'host-status.json',
                    'sync-status.json', 'publication-status.json', 'originals-publication.json', 'STOP'}
        for path in sorted(work.rglob('*')):
            if (not path.is_file() or set(path.relative_to(work).parts) & excluded or
                    path.name in volatile or any('.partial' in part for part in path.relative_to(work).parts) or
                    path.suffix in ('.lock', '.tmp', '.log') or path.name.startswith('.')):
                continue
            role = 'replay' if path.suffix.lower() == '.mp4' else 'process'
            if 'boundaries' in path.parts:
                role = 'checkpoint'
            elif path.name in ('computation-complete.json', 'verified-results.json'):
                role = 'result'
            study.attach(path, role)
        status = study.sync(strict=True)
        atomic_json(work / 'originals-publication.json', {
            'phase': 'originals-published', 'last_boundary': read(work / 'subject/latest.json')['boundary_sha256'],
            'analysis_sha256': sha(work / 'analysis/verified-results.json'),
            'export_sha256': sha(work / 'replays/export.json'), 'pending': status['pending']})
        return status
    if action != 'reports':
        raise ValueError('select originals or reports')
    review_path = work / 'analysis' / 'report-review.json'
    if not review_path.exists():
        raise ValueError('independent evidence, video and report review receipt required')
    review = read(review_path)
    if not all(review.get(key) is True for key in ('continuity_verified', 'video_verified', 'reports_reviewed')):
        raise ValueError('continuity, video and report review must all be complete')
    for lang in ('zh', 'en'):
        path = HERE / f'report.{lang}.md'
        if not path.exists():
            raise ValueError('reviewed report missing: ' + str(path))
        study.text('report:' + lang, 'report', 'E69 连续眼动手眼形色报告 / Final report ' + lang,
                   path.read_text(encoding='utf-8'))
        notes = HERE / f'notes.{lang}.md'
        if notes.exists():
            study.text('notes:' + lang, 'note', 'E69 实验札记 / Research notes ' + lang,
                       notes.read_text(encoding='utf-8'))
    study.attach(review_path, 'result')
    study.sync(strict=True)
    request = study.rid('finalize')
    study.recorder.finalize('completed', request_id=request)
    study.sync(strict=True)
    receipt = read(study.recorder.control / 'receipts' / (request + '.json'))
    atomic_json(work / 'publication-status.json', {'phase': 'completed', 'request_id': request,
                                                 'receipt': receipt['result'], 'pending': 0})
    return receipt['result']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('originals', 'reports'))
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--design', type=Path)
    args = parser.parse_args()
    study = ResearchStudy(args.work, args.design)
    try:
        with study.storage.writer(RESOURCE):
            publish(study, args.action)
    finally:
        study.close()


if __name__ == '__main__':
    main()
