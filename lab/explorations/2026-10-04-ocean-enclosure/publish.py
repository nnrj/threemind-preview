"""Publish scoped E37 reports/video to the local Lab; raw records stay local."""
import json
from urllib.parse import quote
import re

from experiment import HERE,ROOT,WORK

from psycopg.conninfo import conninfo_to_dict
from threemind_lab.config import Settings
from lab.tools.study_publication import Publication,ArchivedStudy
from lab.tools.evidence_archive import artifact_once
from lab.tools.ocean_cli import read_json,write_json


def links(body):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if url.endswith('.md') and not url.startswith(('/','http','#')):
            url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def main():
    d=conninfo_to_dict(Settings.from_env().database_url)
    if (d.get('host'),d.get('port'),d.get('dbname'))!=('127.0.0.1','5433','threemind'):
        raise RuntimeError('verified local ThreeMind database required')
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            body=re.sub(r'!\[[^\]]*\]\(figures/process.png\)',p.image('E37-process',HERE/'figures/process.png'),body)
            p.document('report:'+lang,'report','E37 包裹吞食与代际变化 / Enclosure and generations '+lang,body)
            p.note('findings:'+lang,'E37 Findings '+lang,body)
        p.note('execution','E37 执行记录 / Execution',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        content=['# E37 全意识驱动 · 仅包裹吞食 / All-Core enclosure-only']
        for item in read_json(WORK/'media/catalog.json')['clips']:
            video=WORK/item['video'];p.guard(reserve=video.stat().st_size)
            a=artifact_once(p,'video:'+item['id'],video,item['title'],'video/mp4',
                metadata={'complete_habitat':True,'controllers':'all-core','predation':'complete-enclosure-only'})
            content += [item['title'],item['description'],p.image('E37-'+item['id'],WORK/item['poster']),
                f'[MP4](/api/v2/projects/{s.project}/artifacts/{a["artifact_id"]})']
        p.document('record:videos','record','E37 实测全景与吞食录像 / Measured footage','\n\n'.join(content))
        p.document('record:evidence','record','E37 原始证据位置 / Local raw evidence',
            f'Raw inputs, world and brain snapshots: `{WORK}`.\n\n'+
            '原始数据保留在独立本地目录，本轮不重复打包复制，也不扫描旧实验。\n\n'+links('[操作 / Commands](README.md)'))
        delivery={'project':s.project,'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
            'raw_path':str(WORK),'raw_uploaded':False,'duplicate_raw_archive':False,
            'work_bytes':sum(x.stat().st_size for x in WORK.rglob('*') if x.is_file())}
        write_json(HERE/'delivery.json',delivery);print(json.dumps(delivery))
    finally:s.db.close()


if __name__=='__main__':main()
