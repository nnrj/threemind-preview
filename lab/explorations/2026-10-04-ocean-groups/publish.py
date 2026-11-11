"""Publish scoped E35-E36 findings/media only to the verified local Lab."""
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
                body=re.sub(r'!\[[^\]]*\]\(figures/'+re.escape(figure.name)+r'\)',p.image('E35-E36-'+figure.stem,figure),body)
            p.document('report:'+lang,'report','E35-E36 整组比较与共海竞争 / Whole-group and shared competition '+lang,body)
            p.note('findings:'+lang,'E35-E36 结论 / Findings '+lang,body)
        p.note('execution','E35-E36 执行记录',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        catalog=WORK/'media/catalog.json'
        if catalog.exists():
            content=['# E35-E36 完整海洋群体竞争 / Measured shared-ocean competition']
            for item in read_json(catalog)['clips']:
                a=artifact_once(p,'video:'+item['id'],WORK/item['video'],item['title'],'video/mp4',
                    metadata={'complete_habitat':True,'schema':'threemind.measured-video/1'})
                content.extend([item['title'],item['description'],p.image(item['id'],WORK/item['poster']),
                    f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})'])
            p.document('record:videos','record','E35-E36 实测影片 / Measured footage','\n\n'.join(content))
        archive,members=prepare_archive(p,historical_scope=('Copied E32 whole-world sources; newly generated mixed worlds',))
        p.document('record:evidence','record','E35-E36 本地证据 / Local evidence',f'Full raw evidence remains local: `{archive}`\n\n'+links('[Commands](README.md)'))
        result={'project':s.project,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'members':members,'database_upload':False},
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))}}
        if not (HERE/'delivery.json').exists():write_json(HERE/'delivery.json',result)
        print(json.dumps(result))
    finally:s.db.close()


if __name__=='__main__':publish()
