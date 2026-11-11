import json
import re
from urllib.parse import quote
from experiment import HERE,ROOT,WORK
from lab.tools.study_publication import Publication,ArchivedStudy
from lab.tools.evidence_archive import artifact_once
from lab.tools.ocean_cli import read_json,write_json


def main():
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        table=artifact_once(p,'results',HERE/'results.json','E38 results','application/json')
        turns=artifact_once(p,'turning-results',HERE/'turning-results.json','E38 turning candidates','application/json')
        artifacts={'results.json':table,'turning-results.json':turns}
        def link(m):
            label,url=m.group(1),m.group(2)
            if url in artifacts:url=f'/api/v2/projects/{s.project}/artifacts/{artifacts[url]["artifact_id"]}'
            elif url.endswith('.md') and not url.startswith(('/','http','#')):
                url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
            return f'[{label}]({url})'
        for lang in ('zh','en'):
            body=(HERE/f'report.{lang}.md').read_text(encoding='utf-8')
            body=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,body)
            p.document('report:'+lang,'report','E38 物种候选与营养选择 / Candidate selection '+lang,body)
            p.note('findings:'+lang,'E38 Findings '+lang,body)
        closeout=(HERE/'turning-and-closeout.md').read_text(encoding='utf-8')
        closeout=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,closeout)
        p.document('record:turning','record','E38 转弯摄食候选与结项 / Turning candidates and closeout',closeout)
        p.note('findings:turning','E38 转弯摄食与后续选择 / Turning and next selection',closeout)
        body=['# E38 · 实测完整海洋 / Measured complete habitats']
        for item in read_json(WORK/'media/catalog.json')['clips']:
            path=WORK/item['video'];p.guard(reserve=path.stat().st_size)
            a=artifact_once(p,'video:'+item['id'],path,item['title'],'video/mp4',
                metadata={'complete_habitat':True,'all_core':True,'predation':'enclosure-only'})
            body += [item['title'],item['description'],p.image('E38-'+item['id'],WORK/item['poster']),
                     f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})']
        p.document('record:videos','record','E38 候选谱系全景录像 / Full-habitat footage','\n\n'.join(body))
        p.document('record:raw','record','E38 原始证据 / Raw evidence',
            f'Local raw evidence: `{WORK}`. Complete snapshots, event species, inputs, trajectories and actions are retained. No duplicate bulk archive.')
        write_json(HERE/'delivery.json',{'project':s.project,'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
                    'raw_path':str(WORK),'raw_uploaded':False,'work_bytes':sum(x.stat().st_size for x in WORK.rglob('*') if x.is_file())})
        print('E38 publication complete')
    finally:s.db.close()


if __name__=='__main__':main()
