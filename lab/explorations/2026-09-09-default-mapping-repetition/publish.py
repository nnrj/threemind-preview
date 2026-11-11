"""Publish this study's records, notebook, raw indexes and report through Lab."""
import importlib.util
from pathlib import Path

from run import HERE, WORK, META
from threemind_lab import notebooks, report_exports
from threemind_lab.database import LOCAL_USER

path = HERE.parent / '2026-09-09-calibrated-generalization' / 'publish.py'
loader = importlib.util.spec_from_file_location('blocked_publisher_base', path)
base = importlib.util.module_from_spec(loader)
loader.loader.exec_module(base)
base.HERE, base.WORK, base.META = HERE, WORK, META
base.WORKER = 'default-mapping-repetition-publisher'
commentary = base.commentary


class Publisher(base.Publisher):
    def __init__(self):
        super().__init__()
        self.capabilities['executor']=str(Path(__file__).relative_to(HERE.parents[2]))
        self.db.announce_worker(base.WORKER,self.capabilities)

    def publish(self):
        item = self.entry('evidence_upload')
        if not item.get('done'):
            if not item.get('job_id'):
                job = self.db.enqueue(self.project, 'analysis',
                                      {'executor': self.capabilities['executor'], 'purpose': 'archive completed experiment'})
                item['job_id'] = str(job['id'])
                self.flush()
            job = self.claim_owned(item['job_id'])
            for file in sorted(WORK.glob('*-results.json')):
                self.artifact(job, file, 'application/json')
            for name in ['protocol.md', 'curriculum.json', 'preflight.json', 'implementation.json', 'run.py', 'analyze.py', 'verify.py',
                         'publish.py', 'make_report.py', 'structure.py', 'edge-continuity.json',
                         'paired_control.py', 'pair-control-plan.md', 'raw_activity.py', 'raw-activity-differences.json',
                         'report-conclusion.md', 'interpretation.en.md', 'validation-notes.md',
                         'summary.json', 'measurements.json', 'training-traces.json',
                         'time-courses.json', 'evidence-index.json', 'acceptance-prepublish.json',
                         'report.md', 'report.en.md', 'README.md']:
                file = HERE / name
                if file.exists():
                    self.artifact(job, file, 'application/json' if file.suffix == '.json' else 'text/plain; charset=utf-8')
            self.artifact(job, HERE.parent / '2026-09-09-calibrated-generalization' / 'implementation-source.zip',
                          'application/zip')
            self.db.finish(job, result={'archived': True})
            item['done'] = True
            self.flush()
        images = {}
        for name in ['training.png', 'learning.png', 'family-curves.png']:
            item = self.entry('image:' + name)
            notebooks.save_asset(self.db, self.project, LOCAL_USER, item['id'], name, (HERE/name).read_bytes())
            images[name] = f"/api/v2/projects/{self.project}/note-assets/{item['id']}"
        def rich(text):
            for name, url in images.items():
                text = text.replace('](' + name + ')', '](' + url + ')')
            return text
        links = '\n'.join(f"- [{key[9:]}](/api/v2/projects/{self.project}/artifacts/{v['artifact_id']})"
                          for key, v in self.state.items() if key.startswith('artifact:'))
        records = []
        for key, title in [('training', '逐句教学记录：实际重复次数与连接保持'),
                           ('memory', '配对与问答记录：分阶段活动'),
                           ('family', '关系组合记录：未见家系与交叉对照')]:
            record = self.document(key, 'record', title, [],
                                   [commentary('content', rich((HERE/(key+'-record.md')).read_text(encoding='utf-8'))),
                                    commentary('evidence', links, 'other')])
            records.append({'id': key, 'type': 'record_block', 'record_id': record,
                            'revision': 1, 'block_id': 'content'})
        intro = rich((HERE/'report-intro.md').read_text(encoding='utf-8'))
        conclusion = (HERE/'report-conclusion.md').read_text(encoding='utf-8') + '\n\n' + (HERE/'report-resources.md').read_text(encoding='utf-8')
        report = self.document('report', 'report', '默认映射复验报告：逐句20次与完整标点（2026-09-09）', [],
                               [commentary('intro', intro, 'methods'), *records,
                                commentary('conclusion', conclusion, 'discussion'),
                                commentary('evidence', links, 'other')])
        note = self.entry('note:results')
        if not note.get('revision'):
            saved = notebooks.save_note(self.db, self.project, LOCAL_USER, note['id'], {
                'operation_id': note['operation_id'], 'expected_revision': 0, 'kind': 'note',
                'collection_id': self.meta['notebook_id'], 'title': '默认映射逐句教学：完整报告、训练清单与原始证据',
                'body': {'format': 'markdown', 'text': rich((HERE/'report.md').read_text(encoding='utf-8'))
                         + '\n\n## 原始证据\n\n' + links}})
            note.update(revision=saved['revision'], content_hash=saved['content_hash'])
            self.flush()
        for fmt in ['markdown', 'html']:
            item = self.entry('export:' + fmt)
            self.service_job(item, lambda item=item, fmt=fmt: report_exports.request(
                self.db, self.project, LOCAL_USER, report,
                {'operation_id': item['operation_id'], 'revision': 1, 'format': fmt,
                 'language': 'zh-CN', 'include_data': True}), report_exports.execute)
        print('Three records, one linked report, notebook, Markdown and HTML exports saved.')


if __name__ == '__main__':
    publisher = Publisher()
    try:
        publisher.publish()
    finally:
        publisher.db.close()
