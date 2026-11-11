"""Publish this completed study using the existing evidence and report services."""
import importlib.util
import json
import analyze as analysis_entry
from run import HERE,ROOT,WORK,META,encoded
from threemind_lab import notebooks,report_exports
from threemind_lab.database import LOCAL_USER

# The reusable publisher imports an analysis callable but does not invoke it.
analysis_entry.analyze=analysis_entry.base.analyze
path=HERE.parent/'2026-09-10-temporal-repetition/publish.py'
loader=importlib.util.spec_from_file_location('temporal_publication',path)
base=importlib.util.module_from_spec(loader);loader.loader.exec_module(base)
base.base.WORKER='host-background-pair-publication'


class Publisher(base.Publisher):
    def publish(self):
        data=json.loads((HERE/'analysis.json').read_bytes())
        entry=self.entry('archive')
        if not entry.get('done'):
            job=self.db.enqueue(self.project,'analysis',dict(executor=str(HERE.relative_to(ROOT)/'publish.py'),
                purpose='archive completed host-background study; no model changes'))
            entry['job_id']=str(job['id']);self.flush();owned=self.claim_owned(entry['job_id'])
            for directory in (HERE,WORK):
                for file in sorted(directory.iterdir()):
                    if file.is_file() and file.name not in ('platform.json','closure.json'):
                        mime={'.json':'application/json','.png':'image/png','.zip':'application/zip',
                              '.html':'text/html; charset=utf-8'}.get(file.suffix,'text/plain; charset=utf-8')
                        self.artifact(owned,file,mime)
            self.db.finish(owned,result={'archived':True});entry['done']=True;self.flush()
        image=self.entry('image')
        notebooks.save_asset(self.db,self.project,LOCAL_USER,image['id'],'results.png',(HERE/'results.png').read_bytes())
        body=(HERE/'report.md').read_text(encoding='utf-8').replace('](results.png)',
            f"](/api/v2/projects/{self.project}/note-assets/{image['id']})")
        for key,value in self.state.items():
            if key.startswith('artifact:'):
                body=body.replace(']('+key[9:]+')',f"](/api/v2/projects/{self.project}/artifacts/{value['artifact_id']})")
        measurements=[s for p in sorted(WORK.glob('seed-*-results.json')) for s in json.loads(p.read_bytes())['rows']]
        for group,title in [('forward','正向配对'),('reverse','反向配对')]:
            sources=[];blocks=[base.commentary('intro','背景0.25、文本0.9、线索0.5；未修改读出器。以下包含零强度对照；衰减窗口不能当作收敛答案。')]
            for s in measurements:
                if group not in s['measurements']:continue
                key=f"{s['seed']}-{s['stage']}-{group}";source=self.temporal_source(key,s['measurements'][group]['id'])
                sources.append(source);blocks.append(dict(id='table-'+key,type='table',source=source,
                    metrics=['converged','response_seconds','node_count','candidate_count','sample_count'],title=key))
            self.document(group,'record',title+'：宿主背景与10秒间隔',sources,blocks)
        c=next(c for c in data['cases'] if c['seed']==41701 and c['stage']=='each20' and c['cue']=='甲是' and c['dose']==.5)
        nodes=self.temporal_source('example-nodes',c['calibration_id'],'temporal_nodes',[c['window_id']])
        series=self.temporal_source('example-series',c['calibration_id'],'temporal_series',[c['window_id']])
        report=self.document('report','report','宿主背景配对复验：维持存活，文本响应仍衰减',[nodes,series],[
            base.commentary('main',body),base.commentary('ordering','原始rank是已有综合排名；完整窗末强度排序请打开报告中的排名查看器。'),
            dict(id='nodes',type='table',source=nodes,metrics=['last_activation','peak_activation','score','rank'],title='原始节点指标：41701 / 甲是'),
            dict(id='series',type='chart',source=series,metric='total',chart='line',title='原读出器超基线响应总量（不是全网激活）')])
        note=self.entry('note:results')
        if not note.get('revision'):
            saved=notebooks.save_note(self.db,self.project,LOCAL_USER,note['id'],dict(operation_id=note['operation_id'],
                expected_revision=0,kind='note',collection_id=self.meta['notebook_id'],title='结果：宿主背景确实接入，文本部分未保持激活',
                body={'format':'markdown','text':body}))
            note.update(revision=saved['revision'],content_hash=saved['content_hash']);self.flush()
        for fmt in ('markdown','html'):
            item=self.entry('export:'+fmt)
            self.service_job(item,lambda item=item,fmt=fmt:report_exports.request(self.db,self.project,LOCAL_USER,report,
                dict(operation_id=item['operation_id'],revision=1,format=fmt,language='zh-CN',include_data=True)),report_exports.execute)
        print('Published study records, report, note, raw recording, all rankings and exports.')


if __name__=='__main__':
    p=Publisher()
    try:p.publish()
    finally:p.db.close()
