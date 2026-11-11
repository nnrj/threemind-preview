"""Publish scoped E34 findings/media only to the verified local Lab."""
import json
import re
from urllib.parse import quote
from psycopg.conninfo import conninfo_to_dict
from threemind_lab.config import Settings
from experiment import HERE,ROOT,WORK,study
from lab.tools.study_publication import Publication
from lab.tools.evidence_archive import prepare_archive,artifact_once
from lab.tools.ocean_cli import write_json,read_json


def links(body):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if url.endswith('.md') and not url.startswith(('/','http','#')):
            url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def publish():
    d=conninfo_to_dict(Settings.from_env().database_url)
    if (d.get('host'),d.get('port'),d.get('dbname'))!=('127.0.0.1','5433','threemind'):
        raise RuntimeError('verified local destination required')
    s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            for figure in (HERE/'figures').glob('*.png'):
                body=re.sub(r'!\[[^\]]*\]\(figures/'+re.escape(figure.name)+r'\)',p.image('E34-'+figure.stem,figure),body)
            p.document('report:'+lang,'report','E34 捕获归因 / Capture attribution '+lang,body)
            p.note('findings:'+lang,'E34 结论 / Findings '+lang,body)
        p.note('execution','E34 执行记录',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        catalog=WORK/'media/catalog.json'
        if catalog.exists():
            content=['# E34 完整环境的实测遭遇 / Measured full-habitat encounters']
            for item in read_json(catalog)['clips']:
                a=artifact_once(p,'video:'+item['id'],WORK/item['video'],item['title'],'video/mp4',
                    metadata={'complete_habitat':True,'schema':'threemind.measured-video/1'})
                content.extend([item['title'],item['description'],p.image(item['id'],WORK/item['poster']),
                    f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})'])
            p.document('record:videos','record','E34 实测影片 / Measured footage','\n\n'.join(content))
        archive,members=prepare_archive(p,historical_scope=('Copied E32 whole-world sources are explicitly declared',))
        p.document('record:evidence','record','E34 本地证据 / Local evidence',f'Full raw evidence remains local: `{archive}`\n\n'+links('[Commands](README.md)'))
        result={'project':s.project,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'members':members,'database_upload':False},
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))}}
        if not (HERE/'delivery.json').exists():write_json(HERE/'delivery.json',result)
        print(json.dumps(result))
    finally:s.db.close()


if __name__=='__main__':publish()
