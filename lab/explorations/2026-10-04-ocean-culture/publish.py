"""Publish existing evidence and reports, without advancing an experiment."""
import re
from urllib.parse import quote
from experiment import HERE,ROOT,WORK
from lab.tools.study_publication import Publication,ArchivedStudy
from lab.tools.evidence_archive import artifact_once
from lab.tools.ocean_cli import read_json,write_json


def main():
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        table=artifact_once(p,'results',HERE/'results.json','E39–E40 results','application/json')
        def link(m):
            label,url=m.group(1),m.group(2)
            if url=='results.json':url=f'/api/v2/projects/{s.project}/artifacts/{table["artifact_id"]}'
            elif url.endswith('.md') and not url.startswith(('/','http','#')):
                url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
            return f'[{label}]({url})'
        for lang in ('zh','en'):
            body=(HERE/f'report.{lang}.md').read_text(encoding='utf-8')
            body=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,body)
            p.document('report:'+lang,'report','E39–E40 混合培养与邻近分享 / Culture and sharing '+lang,body)
            p.note('findings:'+lang,'E39–E40 Findings '+lang,body)
        body=['# E39–E40 · 实测完整海洋 / Measured complete habitats']
        for item in read_json(WORK/'media/catalog.json')['clips']:
            path=WORK/item['video'];p.guard(reserve=path.stat().st_size)
            a=artifact_once(p,'video:'+item['id'],path,item['title'],'video/mp4',
                metadata={'complete_habitat':True,'all_core':True,'predation':'enclosure-only'})
            body += [item['title'],item['description'],p.image('E39-'+item['id'],WORK/item['poster']),
                     f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})']
        p.document('record:videos','record','E39–E40 全景与行为录像 / Habitat and behavior footage','\n\n'.join(body))
        p.document('record:raw','record','E39–E40 原始证据 / Raw evidence',
            f'Local raw evidence: `{WORK}`. Full-world snapshots, inputs, trajectories, actions and passive candidate archives are retained. No duplicate bulk upload.')
        write_json(HERE/'delivery.json',{'project':s.project,
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
            'raw_path':str(WORK),'raw_uploaded':False,
            'work_bytes':sum(x.stat().st_size for x in WORK.rglob('*') if x.is_file())})
        print('E39–E40 publication complete')
    finally:s.db.close()


if __name__=='__main__':main()
