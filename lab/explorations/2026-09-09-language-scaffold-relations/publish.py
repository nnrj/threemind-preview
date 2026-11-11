"""Publish only this study through the existing Lab note/report/evidence services."""
import importlib.util
import json
from pathlib import Path

from analyze import analyze
from run import HERE, ROOT, WORK, META
from threemind_lab import notebooks, report_exports
from threemind_lab.database import LOCAL_USER

path = HERE.parent/'2026-09-09-calibrated-generalization'/'publish.py'
spec = importlib.util.spec_from_file_location('previous_publisher', path)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
previous.HERE, previous.WORK, previous.META = HERE, WORK, META
previous.WORKER = 'language-scaffold-publisher'
previous.TITLES = {'rules': '完整教学与规则打乱的活动对比', 'teaching': '完整教学与辅助教学打乱的活动对比'}
commentary = previous.commentary


class Publisher(previous.Publisher):
    def publish(self):
        summary = analyze()
        item = self.entry('evidence_upload')
        if not item.get('done'):
            if not item.get('job_id'):
                job = self.db.enqueue(self.project, 'analysis', {'executor': self.capabilities['executor'],
                                      'purpose': 'archive existing study evidence only'})
                item['job_id'] = str(job['id'])
                self.flush()
            job = self.claim_owned(item['job_id'])
            for file in sorted(WORK.glob('*-results.json')):
                self.artifact(job, file, 'application/json')
            for name in ['protocol.md', 'amendment.md', 'preflight.json', 'physical-timing.json',
                         'calibration-decision.json', 'instrument-decision.json', 'summary.json',
                         'evidence-index.json', 'acceptance-prepublish.json', 'report.md', 'report.en.md',
                         'family-cases.csv', 'probe-observability.csv', 'run.py', 'analyze.py',
                         'run_diagnostic.py', 'weak_probe.py', 'decide_instrument.py', 'check_design.py',
                         'check_analysis.py', 'diagnose_calibration.py', 'verify_evidence.py', 'curves.py',
                         'time-courses.json', 'README.md']:
                p = HERE/name
                if p.exists():
                    self.artifact(job, p, 'application/json' if p.suffix=='.json' else 'text/plain; charset=utf-8')
            self.artifact(job, HERE.parent/'2026-09-09-calibrated-generalization'/'implementation-source.zip',
                          'application/zip')
            self.db.finish(job, result={'archived': True})
            item['done'] = True
            self.flush()
        sources = {key: self.source(key, self.analysis(key, val)) for key,val in summary['analyses'].items()}
        text = (HERE/'report.md').read_text(encoding='utf-8')
        for filename in ['results.png','time-courses.png']:
            image = self.entry('image:'+filename)
            notebooks.save_asset(self.db, self.project, LOCAL_USER, image['id'], filename, (HERE/filename).read_bytes())
            text = text.replace(']('+filename+')', f"](/api/v2/projects/{self.project}/note-assets/{image['id']})")
        links = '\n'.join(f"- [{key[9:]}](/api/v2/projects/{self.project}/artifacts/{v['artifact_id']})"
                          for key,v in self.state.items() if key.startswith('artifact:'))
        text += '\n\n## 可复查证据\n\n' + links
        self.document('calibration', 'record', '实验记录：丰富教学后的探针校准与饱和诊断', [], [
            commentary('description', (HERE/'amendment.md').read_text(encoding='utf-8'), 'methods'),
            commentary('decision', json.dumps(json.loads((HERE/'instrument-decision.json').read_bytes()),
                                              ensure_ascii=False, indent=2), 'results'),
            commentary('evidence', links, 'other')])
        refs = []
        for key in sources:
            blocks = [
                commentary('limits', summary['analyses'][key]['inference'], 'methods'),
                {'id': 'chart', 'type': 'chart', 'source': sources[key], 'metric': 'difference', 'chart': 'bar',
                 'analysis_metric': 'query_role_specificity', 'title': previous.TITLES[key]},
                {'id': 'table', 'type': 'table', 'source': sources[key], 'metrics': previous.METRICS,
                 'title': '编码种子块的活动对比，非语言准确率'},
                commentary('interpretation', (HERE/'interpretation.md').read_text(encoding='utf-8'), 'discussion'),
            ]
            ident = self.document(key, 'record', previous.TITLES[key], [sources[key]], blocks)
            refs.extend({'id': key+'_'+b, 'type': 'record_block', 'record_id': ident, 'revision': 1, 'block_id': b}
                        for b in ['chart','table'])
        report = self.document('report', 'report', '教学探索报告：父亲的父亲与问答迁移（2026-09-09）', [],
                               [commentary('report', text, 'discussion'), *refs])
        note = self.entry('note:results')
        if not note.get('revision'):
            saved = notebooks.save_note(self.db, self.project, LOCAL_USER, note['id'], {
                'operation_id': note['operation_id'], 'expected_revision': 0, 'kind': 'note',
                'collection_id': self.meta['notebook_id'], 'title': '教学探索：完整报告、图表和证据',
                'body': {'format':'markdown','text':text}})
            note.update(revision=saved['revision'], content_hash=saved['content_hash'])
            self.flush()
        for fmt in ['markdown','html']:
            item = self.entry('export:'+fmt)
            self.service_job(item, lambda item=item,fmt=fmt: report_exports.request(
                self.db,self.project,LOCAL_USER,report,{'operation_id':item['operation_id'],'revision':1,
                                                       'format':fmt,'language':'zh-CN','include_data':True}),
                report_exports.execute)
        self.flush()
        print('Report, three records, notebook and Markdown/HTML exports saved.', flush=True)


if __name__ == '__main__':
    p = Publisher()
    try:
        p.publish()
    finally:
        p.db.close()
