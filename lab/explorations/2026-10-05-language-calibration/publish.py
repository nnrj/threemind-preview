"""Publish only this project's documents/evidence using the public Lab services."""
import re
import shutil
from urllib.parse import quote

from experiment import HERE, ROOT, WORK, read_json

from lab.tools.evidence_archive import archive_once, artifact_once
from lab.tools.service_study import new_json
from lab.tools.study_publication import ArchivedStudy, Publication


def main():
    study=ArchivedStudy(WORK);study.name=study.settings.name;publication=Publication(study)
    try:
        artifacts={}
        for key,path,mime in (
            ('results',HERE/'results.json','application/json'),
            ('viewer',WORK/'language-calibration.html','text/html'),
            ('figure',HERE/'findings.png','image/png'),('vector',HERE/'findings.svg','image/svg+xml'),
            ('influence',HERE/'learned-influence.png','image/png'),('influence-vector',HERE/'learned-influence.svg','image/svg+xml')):
            artifacts[key]=artifact_once(publication,key,path,'E45 '+key,mime)
        def links(match,base=HERE):
            label,url=match.group(1),match.group(2)
            key={'results.json':'results','findings.png':'figure','findings.svg':'vector',
                 'learned-influence.png':'influence','learned-influence.svg':'influence-vector',
                 '../../../.work/language-calibration-20261005/language-calibration.html':'viewer'}.get(url)
            if key:url=f"/api/v2/projects/{study.project}/artifacts/{artifacts[key]['artifact_id']}"
            elif url.endswith('.md') and not url.startswith(('http','/','#')):
                url='/docs?doc='+quote((base/url).resolve().relative_to(ROOT).as_posix(),safe='')
            return f'[{label}]({url})'
        def render(path):
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda match:links(match,path.parent),path.read_text(encoding='utf-8'))
        for language in ('zh','en'):
            body=render(HERE/f'report.{language}.md')
            publication.document('report:'+language,'report','E45 语言校准、通感与回放 / Language calibration '+language,body)
            publication.note('findings:'+language,'E45 Results '+language,body)
            publication.note('execution-final:'+language,'E45 Execution and limits '+language,render(HERE/f'delivery.{language}.md'))
            publication.note('discussion-final:'+language,'E45 Native patterns and expression '+language,
                render(ROOT/f'docs/{language}/plans/language-calibration-and-composition.md'))
        publication.document('record:continuous','record','E45 教学后的真实连续活动 / Post-teaching activity',
            f"[300秒连续感官活动与原样文字 / Continuous sensory activity and raw words](/api/v2/projects/{study.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            '每条曲线来自同一连续来源；背景保留，无新教学。原始轨迹及半秒原文保留；无晚期回放候选，未执行其干预。提示后的局部屏蔽另见报告。 / Each source is one continuous history with background and no new teaching. Raw trajectories/text are retained; no late replay candidate, so no replay intervention ran. Cued localized interventions are separate report evidence.')
        # Keep the final derived JSON/SVG and discussion beside the raw work
        # before the one-pass archive; ordinary source archiving omits JSON/SVG.
        copies=WORK/'final-artifacts'
        copies.mkdir(exist_ok=True)
        for source in sorted(HERE.iterdir()):
            if source.is_file() and source.suffix in ('.json','.svg'):
                target=copies/source.name
                if not target.exists():shutil.copy2(source,target)
        for language in ('zh','en'):
            target=copies/f'discussion.{language}.md'
            if not target.exists():
                shutil.copy2(ROOT/f'docs/{language}/plans/language-calibration-and-composition.md',target)
        archive=archive_once(publication,'E45 reproducible evidence.zip')
        publication.document('record:evidence','record','E45 完整证据 / Complete evidence',
            f"[Evidence ZIP](/api/v2/projects/{study.project}/artifacts/{archive['artifact_id']})\n\n"
            '独立校准及正式种子、冻结选择、输入剂量、课程、背景、完整匿名过程、快照、表达模型与干预结果。 / Calibration and held-out seeds, frozen selections, doses, teaching, background, full anonymous processes, snapshots, expression models and interventions.')
        if not (HERE/'delivery.json').exists():
            new_json(HERE/'delivery.json',{'project':study.project,'documents':{k:v['id'] for k,v in publication.state.items() if k.startswith(('report:','record:'))},
                'archive':archive,'artifacts':artifacts,'raw_path':str(WORK),'completed_cases':read_json(HERE/'results.json')['completed_cases']})
        publication.guard()
        print('E45 publication complete')
    finally:study.db.close()


if __name__=='__main__':main()
