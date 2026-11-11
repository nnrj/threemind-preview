"""Publish completed pair experiments through existing native report services."""
import hashlib
import importlib.util
import json
import re
from run import HERE,ROOT,WORK,META,encoded,sha
from threemind_lab import notebooks,report_exports
from threemind_lab.database import LOCAL_USER

path=HERE.parent/'2026-09-10-temporal-repetition/publish.py'
loader=importlib.util.spec_from_file_location('prior_temporal_publication',path)
prior=importlib.util.module_from_spec(loader);loader.loader.exec_module(prior)
prior.base.WORKER='pair-no-punctuation-20260910-publication'


class Publisher(prior.Publisher):
    def __init__(self):
        super().__init__()
        self.capabilities['executor']=str(HERE.relative_to(ROOT)/'publish.py')
        self.db.announce_worker(prior.base.WORKER,self.capabilities)

    def publish(self):
        data=json.loads((HERE/'analysis.json').read_bytes())
        journal=self.entry('archive')
        if not journal.get('done'):
            if not journal.get('job_id'):
                job=self.db.enqueue(self.project,'analysis',dict(executor=self.capabilities['executor'],
                    purpose='archive completed standalone pair study; no model changes'))
                journal['job_id']=str(job['id']);self.flush()
            job=self.claim_owned(journal['job_id'])
            for file in sorted(HERE.iterdir()):
                if file.is_file() and file.name not in ('platform.json','quota-monitor.json','acceptance.json'):
                    mime={'.json':'application/json','.png':'image/png','.zip':'application/zip',
                          '.html':'text/html; charset=utf-8'}.get(file.suffix,'text/plain; charset=utf-8')
                    self.artifact(job,file,mime)
            for file in sorted(WORK.iterdir()):
                if file.is_file() and (file.name.startswith('seed-') or file.name in ('ranking-viewer.png','verify-viewer.cjs')):
                    self.artifact(job,file,'image/png' if file.suffix=='.png' else 'text/plain; charset=utf-8')
            self.db.finish(job,result={'archived':True});journal['done']=True;self.flush()
        picture=self.entry('image')
        notebooks.save_asset(self.db,self.project,LOCAL_USER,picture['id'],'pair-results.png',(HERE/'pair-results.png').read_bytes())
        image_url=f"/api/v2/projects/{self.project}/note-assets/{picture['id']}"
        def rich(text):
            text=text.replace('](pair-results.png)',']('+image_url+')')
            for key,value in self.state.items():
                if key.startswith('artifact:'):
                    text=text.replace(']('+key[9:]+')',f"](/api/v2/projects/{self.project}/artifacts/{value['artifact_id']})")
            return text
        report_text=rich((HERE/'report.md').read_text(encoding='utf-8'))
        for group,title in [('forward','正向配对：甲是／乙是／甲／乙'),('reverse','反向配对：松子／铃铛')]:
            sources=[]
            blocks=[prior.commentary('intro','全部阶段和零强度对照如下；完整强度排序见报告附件。converged只代表原读出器收敛，不自动代表配对成功。')]
            for stage in data['stages']:
                raw=next(s for p in sorted(WORK.glob('seed-*-results.json'))
                  for s in json.loads(p.read_bytes())['rows'] if s['checkpoint_id']==stage['checkpoint_id'])
                m=raw['measurements'][group]
                key=f"{stage['seed']}-{stage['arm']}-{stage['stage']}-{group}"
                source=self.temporal_source(key,m['id']);sources.append(source)
                blocks.append(dict(id='table-'+key,type='table',source=source,
                    metrics=['converged','response_seconds','node_count','candidate_count','sample_count'],
                    title=f"{stage['seed']} / {stage['arm']} / {stage['stage']} / {group}：含零刺激"))
            self.document(group,'record',title+'（无标点，每句20／200次）',sources,blocks)
        example=next(c for c in data['cases'] if c['seed']==41701 and c['arm']=='AB'
                     and c['stage']=='each200' and c['cue']=='甲是' and c['dose']==1)
        nodes=self.temporal_source('example-final-nodes',example['calibration_id'],'temporal_nodes',[example['window_id']])
        series=self.temporal_source('example-final-series',example['calibration_id'],'temporal_series',[example['window_id']])
        report=self.document('report','report','松子铃铛配对报告：重复后收敛，终态配对并列',[nodes,series],[
            prior.commentary('main',report_text),
            prior.commentary('reader-note','下面是原始时序来源。原rank是既有综合排名；本轮按窗末激活强度的完整排序，请用报告顶部“排名查看器”。'),
            dict(id='original-nodes',type='table',source=nodes,metrics=['last_activation','peak_activation','score','rank'],
                 title='41701 / AB / 甲是：原始节点指标'),
            dict(id='original-series',type='chart',source=series,metric='total',chart='line',
                 title='原读出器合格超基线响应（不是全部原始激活总和）')])
        note=self.entry('note:results')
        if not note.get('revision'):
            saved=notebooks.save_note(self.db,self.project,LOCAL_USER,note['id'],dict(operation_id=note['operation_id'],
                expected_revision=0,kind='note',collection_id=self.meta['notebook_id'],
                title='实验结果：无标点配对的时序收敛与全节点排名',body={'format':'markdown','text':report_text}))
            note.update(revision=saved['revision'],content_hash=saved['content_hash']);self.flush()
        for fmt in ('markdown','html'):
            item=self.entry('export:'+fmt)
            self.service_job(item,lambda item=item,fmt=fmt:report_exports.request(self.db,self.project,LOCAL_USER,report,
                dict(operation_id=item['operation_id'],revision=1,format=fmt,language='zh-CN',include_data=True)),report_exports.execute)
        print('Published 2 native records, report, notebook, full rankings, and exports.')


if __name__=='__main__':
    publisher=Publisher()
    try:publisher.publish()
    finally:publisher.db.close()
