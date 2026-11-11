"""Publish E32 reports/media to the local Lab; full evidence stays local."""
import json
import re
from urllib.parse import quote
from psycopg.conninfo import conninfo_to_dict
from experiment import HERE,ROOT,WORK,study
from lab.tools.study_publication import Publication
from lab.tools.evidence_archive import prepare_archive,artifact_once
from lab.tools.ocean_cli import read_json,write_json
from threemind_lab.config import Settings


def doc_links(body):
    def convert(m):
        label,url=m.group(1),m.group(2)
        if url.endswith('.md') and not url.startswith(('/','http','#')):
            url='/docs?doc='+quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',convert,body)


def publish():
    destination=conninfo_to_dict(Settings.from_env().database_url)
    if destination.get('host') not in ('127.0.0.1','localhost') or destination.get('port')!='5433' or destination.get('dbname')!='threemind':
        raise RuntimeError('publication restricted to the verified local ThreeMind database')
    s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=doc_links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            for figure in (HERE/'figures').glob('*.png'):
                body=re.sub(r'!\[[^\]]*\]\(figures/'+re.escape(figure.name)+r'\)',p.image('E32-'+figure.stem,figure),body)
            p.document('report:'+lang,'report','E32 完整海洋归因 / Complete-habitat attribution '+lang,body)
            p.note('findings:'+lang,'E32 结论 / Findings '+lang,body)
        p.note('execution-final','E32 执行记录',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        p.note('analysis-registration','E32 指标定义',(HERE/'analysis-registration.md').read_text(encoding='utf-8'))
        gallery=['# E32 完整海洋影片 / Complete-habitat videos',
            '全部影片依据真实记录，保留完整水域、其他个体和营养。近景只是辅助。过程与因果解释请参阅本轮报告。\n\nAll clips preserve the complete habitat; focal insets are supplemental. Causal interpretation is in the report.']
        for item in read_json(WORK/'media/final/catalog.json')['clips']:
            artifact=artifact_once(p,'video:'+item['id'],WORK/item['video'],item['title'],'video/mp4',
                metadata={'schema':'threemind.measured-video/1','description':item['description'],'complete_habitat':True})
            url=f'/api/v2/projects/{s.project}/artifacts/{artifact["artifact_id"]}'
            gallery.extend(['## '+item['title'],p.image(item['id']+'-poster',WORK/item['poster']),
                item['description'],f'[播放或下载 MP4 / Open MP4]({url})'])
        p.document('record:videos','record','E32 完整海洋实测影片 / Measured ocean footage','\n\n'.join(gallery))
        archive,members=prepare_archive(p,historical_scope=('Copied E30 protocol only; no old raw datasets',))
        p.document('record:evidence','record','E32 证据及操作 / Evidence and operations',
            f'完整证据仅保存在本机 / Full evidence retained locally: `{archive}`\n\n'
            '包括新输入、完整群体状态、干预、过程、代码和视频收据。源码/原始证据整包未上传数据库。\n\n'
            +doc_links('[操作说明 / Commands](README.md)'))
        p.guard()
        value={'project':s.project,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'members':members,'database_upload':False},
            'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))}}
        if not (HERE/'delivery.json').exists():write_json(HERE/'delivery.json',value)
        print(json.dumps(value),flush=True)
    finally:s.db.close()


if __name__=='__main__':publish()
