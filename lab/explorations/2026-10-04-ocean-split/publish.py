"""Publish reports and recorded media; do not re-run the simulated habitats."""
import re
from urllib.parse import quote
from experiment import HERE,ROOT,WORK
from lab.tools.study_publication import Publication,ArchivedStudy
from lab.tools.evidence_archive import artifact_once
from lab.tools.ocean_cli import read_json,write_json


def main():
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        table=artifact_once(p,'results',HERE/'results.json','E41 results','application/json')
        def link(m):
            label,url=m.group(1),m.group(2)
            if url=='results.json':url=f'/api/v2/projects/{s.project}/artifacts/{table["artifact_id"]}'
            elif url.endswith('.md') and not url.startswith(('/','http','#')):
                url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
            return f'[{label}]({url})'
        for lang in ('zh','en'):
            body=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,(HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            p.document('report:'+lang,'report','E41 分开培养 / Separate cultivation '+lang,body)
            p.note('findings:'+lang,'E41 Findings '+lang,body)
        body=['# E41 · 实测完整海洋 / Measured complete habitats']
        for item in read_json(WORK/'media/catalog.json')['clips']:
            path=WORK/item['video'];p.guard(reserve=path.stat().st_size)
            a=artifact_once(p,'video:'+item['id'],path,item['title'],'video/mp4',
                metadata={'complete_habitat':True,'all_core':True,
                          'environments':item.get('environments',['threemind.ocean-enclosure/3'])})
            body += [item['title'],item['description'],p.image('E41-'+item['id'],WORK/item['poster']),
                f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})']
        p.document('record:videos','record','E41 全景与行为录像 / Habitat and behavior footage','\n\n'.join(body))
        p.document('record:raw','record','E41 原始证据 / Raw evidence',
            f'Local raw evidence: `{WORK}`. All bodies, food, inputs, actions, snapshots and passive candidate records retained. No duplicate bulk upload.')
        write_json(HERE/'delivery.json',{'project':s.project,
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
            'raw_path':str(WORK),'raw_uploaded':False,
            'work_bytes':sum(x.stat().st_size for x in WORK.rglob('*') if x.is_file())})
        print('E41 publication complete')
    finally:s.db.close()


if __name__=='__main__':main()
