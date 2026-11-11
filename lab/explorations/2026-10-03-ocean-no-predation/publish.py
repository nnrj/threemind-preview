"""Publish the requested no-predation report to the verified local Lab only."""
import json
import re
from urllib.parse import quote
from psycopg.conninfo import conninfo_to_dict
from experiment import HERE,ROOT,WORK,study
from threemind_lab.config import Settings
from lab.tools.study_publication import Publication
from lab.tools.evidence_archive import prepare_archive
from lab.tools.ocean_cli import write_json


def links(body):
    def convert(m):
        label,url=m.group(1),m.group(2)
        if url.endswith('.md') and not url.startswith(('/','http','#')):
            url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',convert,body)


def publish():
    target=conninfo_to_dict(Settings.from_env().database_url)
    if target.get('host') not in ('127.0.0.1','localhost') or target.get('port')!='5433' or target.get('dbname')!='threemind':
        raise RuntimeError('verified local ThreeMind destination required')
    s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            body=re.sub(r'!\[[^\]]*\]\(figures/no-predation.png\)',p.image('E33-no-predation',HERE/'figures/no-predation.png'),body)
            p.document('report:'+lang,'report','E33 禁止吞食 / No predation '+lang,body)
            p.note('findings:'+lang,'E33 结论 / Findings '+lang,body)
        p.note('execution','E33 执行记录',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        archive,members=prepare_archive(p,historical_scope=('Small copied E32 protocols only',))
        p.document('record:evidence','record','E33 本地证据 / Local evidence',
            f'完整原始证据仅保存在本机 / Full raw evidence retained locally: `{archive}`\n\n'
            +links('[操作 / Commands](README.md)'))
        value={'project':s.project,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'members':members,'database_upload':False},
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))}}
        write_json(HERE/'delivery.json',value);print(json.dumps(value))
    finally:s.db.close()


if __name__=='__main__':publish()
