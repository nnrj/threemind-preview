"""Archive this study and publish native temporal sources, records and a report."""
import importlib.util
import json
import zipfile
from pathlib import Path

from run import HERE, ROOT, WORK, META, encoded
from threemind_lab import notebooks, report_exports, report_sources
from threemind_lab.database import LOCAL_USER

path=HERE.parent/'2026-09-09-calibrated-generalization'/'publish.py'
loader=importlib.util.spec_from_file_location('temporal_publication_base',path)
base=importlib.util.module_from_spec(loader)
loader.loader.exec_module(base)
base.HERE,base.WORK,base.META=HERE,WORK,META
base.WORKER='temporal-repetition-20260910-publication'
commentary=base.commentary

class Publisher(base.Publisher):
    def __init__(self):
        super().__init__()
        self.capabilities.update(executor=str(Path(__file__).relative_to(ROOT)),
          features={k:{'state':'available'} for k in ['worker.core','worker.temporal_reports_v1','worker.report_export_v1']})
        self.db.announce_worker(base.WORKER,self.capabilities)

    def temporal_source(self, key, calibration_id, kind='temporal_windows', windows=None):
        item=self.entry('source:'+key)
        metrics={'temporal_windows':['converged','response_seconds','node_count','candidate_count','sample_count'],
                 'temporal_nodes':['last_activation','peak_activation','score','rank'],
                 'temporal_series':['total','active_node_count']}[kind]
        self.service_job(item,lambda:report_sources.request(self.db,self.project,LOCAL_USER,
          dict(operation_id=item['operation_id'],kind=kind,calibration_id=calibration_id,
               metrics=metrics,window_ids=windows or [])),report_sources.capture)
        return item['request_id']

    def publish(self):
        data=json.loads((HERE/'analysis.json').read_bytes())
        evidence=self.entry('evidence_upload')
        if not evidence.get('done'):
            if not evidence.get('job_id'):
                job=self.db.enqueue(self.project,'analysis',{'executor':self.capabilities['executor'],
                  'purpose':'archive completed temporal experiment; no raw-data edits'})
                evidence['job_id']=str(job['id']);self.flush()
            job=self.claim_owned(evidence['job_id'])
            for file in sorted(HERE.iterdir()):
                if file.is_file() and file.name not in ['platform.json','quota-monitor.json']:
                    self.artifact(job,file,'application/json' if file.suffix=='.json' else
                      'image/png' if file.suffix=='.png' else 'application/zip' if file.suffix=='.zip' else 'text/plain; charset=utf-8')
            for file in sorted(WORK.iterdir()):
                if file.is_file() and (file.name.startswith('seed-') or file.name.startswith('diagnostic-')):
                    self.artifact(job,file,'application/json' if file.suffix=='.json' else 'text/plain; charset=utf-8')
            self.db.finish(job,result={'archived':True});evidence['done']=True;self.flush()
        images={}
        for file in sorted(HERE.glob('*.png')):
            item=self.entry('image:'+file.name)
            notebooks.save_asset(self.db,self.project,LOCAL_USER,item['id'],file.name,file.read_bytes())
            images[file.name]=f"/api/v2/projects/{self.project}/note-assets/{item['id']}"
        def rich(text):
            for name,url in images.items():text=text.replace(']('+name+')',']('+url+')')
            for key,value in self.state.items():
                if key.startswith('artifact:'):
                    text=text.replace(']('+key[9:]+')',f"](/api/v2/projects/{self.project}/artifacts/{value['artifact_id']})")
            return text
        links='\n'.join(f"- [{k[9:]}](/api/v2/projects/{self.project}/artifacts/{v['artifact_id']})"
                        for k,v in self.state.items() if k.startswith('artifact:'))
        # Frozen source snapshots are selectable and re-exportable in the report UI.
        selected=[]
        for resultfile in sorted(WORK.glob('seed-*-results.json')):
            for row in json.loads(resultfile.read_bytes())['rows']:
                if (row['arm']=='normal' and row['stage'] in ['dialogue_1','final']) or (
                    row['arm']=='crossed' and row['stage']=='final') or (
                    row['arm']=='swapped' and row['stage']=='dialogue_3'):
                    for group,m in row['measurements'].items():
                        if m['mode']=='temporal' and group in ['pair','family']:
                            selected.append((row,m))
        native_records=[]
        for domain,groups in [('memory',{'pair'}),('family',{'family'})]:
            sources,blocks=[],[commentary('content',rich((HERE/(domain+'-record.md')).read_text(encoding='utf-8')))]
            for row,m in selected:
                if m['group'] not in groups:continue
                key=f"{row['seed']}-{row['arm']}-{row['stage']}-{m['group']}"
                source=self.temporal_source(key,m['id'])
                sources.append(source)
                blocks.append(dict(id='table-'+key,type='table',source=source,
                    metrics=['converged','response_seconds','node_count','candidate_count','sample_count'],
                    title=f"{row['seed']} / {row['arm']} / {row['stage']}：包括零强度对照的全部窗口"))
            ident=self.document(domain,'record',{'memory':'时序配对与问答：阶段、排序及对应互换',
                 'family':'时序家系检验：未见名字与事实交换'}[domain],sources,blocks)
            native_records.append(dict(id=domain,type='record_block',record_id=ident,revision=1,block_id='content'))
        # A concrete raw window gives the user direct access to both final intensity and the old score.
        example=next(c for c in data['cases'] if c['seed']==41701 and c['arm']=='normal' and c['stage']=='final'
                     and c['cue']=='Z的爷爷是谁？' and c['dose']==1)
        ns=self.temporal_source('example-nodes',example['calibration_id'],'temporal_nodes',[example['window_id']])
        ss=self.temporal_source('example-series',example['calibration_id'],'temporal_series',[example['window_id']])
        detail=self.document('raw','record','读出核对：窗口分类、完整节点与时间曲线',[ns,ss],[
            commentary('content',(HERE/'reader-record.md').read_text(encoding='utf-8')),
            dict(id='node-table',type='table',source=ns,metrics=['last_activation','peak_activation','score','rank'],
                 title='原始节点指标；rank是既有综合排名，终态强度并列见说明'),
            dict(id='curve',type='chart',source=ss,metric='total',chart='line',title='窗口内合格超基线响应总量（不是全部激活）')])
        native_records.append(dict(id='raw',type='record_block',record_id=detail,revision=1,block_id='content'))
        report=self.document('report','report','时序收敛复验报告：逐句20次与未见家系（2026-09-10）',[],[
            commentary('intro',rich((HERE/'report-intro.md').read_text(encoding='utf-8')),'purpose'),
            *native_records,
            commentary('conclusion',(HERE/'report-conclusion.md').read_text(encoding='utf-8'),'discussion'),
            commentary('evidence',links)])
        note=self.entry('note:results')
        if not note.get('revision'):
            saved=notebooks.save_note(self.db,self.project,LOCAL_USER,note['id'],dict(
              operation_id=note['operation_id'],expected_revision=0,kind='note',collection_id=self.meta['notebook_id'],
              title='实验结果：时序收敛、激活排序与家系检验',body={'format':'markdown',
              'text':rich((HERE/'report.md').read_text(encoding='utf-8'))+'\n\n## 原始证据\n\n'+links}))
            note.update(revision=saved['revision'],content_hash=saved['content_hash']);self.flush()
        for fmt in ['markdown','html']:
            item=self.entry('export:'+fmt)
            self.service_job(item,lambda item=item,fmt=fmt:report_exports.request(self.db,self.project,LOCAL_USER,report,
              dict(operation_id=item['operation_id'],revision=1,format=fmt,language='zh-CN',include_data=True)),report_exports.execute)
        print('Published temporal records, report, notebook, complete evidence, Markdown and HTML exports.')

if __name__=='__main__':
    publisher=Publisher()
    try:publisher.publish()
    finally:publisher.db.close()
