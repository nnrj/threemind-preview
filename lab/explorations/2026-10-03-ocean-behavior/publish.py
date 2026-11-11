"""E31 publication; no unrelated queue jobs or old evidence are executed/modified."""
import json
import re
import argparse
from urllib.parse import quote
from experiment import WORK,HERE,ROOT,study
from lab.tools.study_publication import Publication
from lab.tools.evidence_archive import archive_once,artifact_once,prepare_archive
from lab.tools.ocean_cli import read_json,write_json


def doc_links(body):
    def replace(m):
        label,url=m.group(1),m.group(2)
        if url.endswith('.md') and not url.startswith(('/','http','#')):
            return f'[{label}](/docs?doc={quote((HERE/url).resolve().relative_to(ROOT).as_posix(),safe="")})'
        return m.group(0)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)


def publish(*,local_evidence=False):
    s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=doc_links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            for figure in (HERE/'figures').glob('*.png'):
                body=re.sub(r'!\[[^\]]*\]\(figures/'+re.escape(figure.name)+r'\)',p.image('E31-'+figure.stem,figure),body)
            p.document('report:'+lang,'report','E31 觅食、追捕、逃离归因 / Behavior attribution '+lang,body)
            p.note('findings:'+lang,'E31 结论 / Findings '+lang,body)
        p.note('execution-final','E31 执行、校正与媒体说明',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        gallery=['# E31 实测行为影片 / Measured behavior clips',
                 '前3段是E31局部装置说明，删去了原群体，不能用作完整生态能力演示；后2段是旧E30原位对照重绘。视频不作为独立样本，不单凭画面判定主动。\n\nThe first three clips illustrate isolated E31 apparatus, not full ecological ability; the original community was removed. The last pair replays old E30 population interventions. Clips are not independent samples.']
        for clip in read_json(WORK/'media/clips-v2/catalog-v2.json')['clips']:
            artifact=artifact_once(p,'video:'+clip['id'],WORK/clip['video'],clip['title'],'video/mp4',
                metadata={'schema':'threemind.measured-video/1','description_zh':clip['description_zh'],'description_en':clip['description_en']})
            url=f'/api/v2/projects/{s.project}/artifacts/{artifact["artifact_id"]}'
            gallery.extend(['## '+clip['title'],p.image(clip['id']+'-poster',WORK/clip['poster']),
                            clip['description_zh']+'\n\n'+clip['description_en'],f'[下载视频 / Download MP4]({url})'])
        p.document('record:videos','record','E31 实测行为录像 / Measured behavior videos','\n\n'.join(gallery))
        historical_scope=(
            'Eight copied E30 donor images and explicitly selected shared-world snapshots',
            'Derived videos of the previously reported E30 individual37 population-intervention event; no old whole archive')
        if local_evidence:
            path,members=prepare_archive(p,historical_scope=historical_scope)
            archive={'local_path':str(path),'bytes':path.stat().st_size,'members':members,'database_upload':False}
            reference=f'本轮完整证据仅本地保存 / Full evidence retained locally: `{path}`.\n\n源码/测试整包未上传数据库；报告、笔记、图表与影片已存入本地研究项目。'
        else:
            archive=archive_once(p,'E31 ocean behavior evidence',historical_scope=historical_scope)
            url=f'/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]}'
            reference=f'[下载本轮证据 / Download study evidence]({url})'
        p.document('record:evidence','record','E31 原始证据与操作 / Evidence and operations',
            reference+'\n\n'
            '包含输入、状态、事前登记、干预、完整过程、工具源码与录像收据。旧实验原件未修改。\n\n'
            +doc_links('[命令与录制说明](README.md)'))
        p.guard()
        answer={'project':s.project,'archive':archive,'reports':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))}}
        if not (HERE/'delivery.json').exists():write_json(HERE/'delivery.json',answer)
        print(json.dumps(answer),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--local-evidence',action='store_true')
    publish(local_evidence=parser.parse_args().local_evidence)
