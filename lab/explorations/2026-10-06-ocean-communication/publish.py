"""Publish E53 once through the ordinary research services; no simulations."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

import psutil
import shutil

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.evidence_archive import archive_once, artifact_once
from lab.tools.ocean_cli import read_json, write_json
from lab.tools.study_publication import ArchivedStudy, Publication
from threemind_lab import research_documents

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/ocean-communication-20261006'


def render(file, artifacts=None):
    def link(match):
        label, url = match.groups()
        if artifacts and url in artifacts:
            url = artifacts[url]
        elif not url.startswith(('http', '/', '#')):
            url = '/docs?doc=' + quote((file.parent / url).resolve().relative_to(ROOT).as_posix(), safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]*)\]\(([^)]+)\)', link, file.read_text(encoding='utf-8'))


def main():
    s = ArchivedStudy(WORK)
    s.name = 'ocean-communication/1'
    # Publication-only amendment, recorded in execution-notes.md. Simulations
    # retain their original 3 GiB stop and 4 GiB ceiling. Here source + ZIP + DB
    # coexist so the evidence can be preserved without deleting source records.
    s.settings.storage_hard = 6 * 2**30
    p = Publication(s)
    try:
        summary = read_json(HERE / 'results.json')
        if any(c['error'] for c in summary['cases']):
            raise RuntimeError('review partial experiment errors before publishing')
        artifacts = {}
        for key, file, mime in (
            ('results', HERE / 'results.json', 'application/json'),
            ('replay', WORK / 'replay.html', 'text/html'),
        ):
            artifacts[key] = artifact_once(p, 'artifact:' + key, file, 'E53 ' + file.name, mime)
        for lang in ('zh', 'en'):
            p.document('report:' + lang, 'report', 'E53 海洋个体间交流 / Embodied communication ' + lang,
                       render(HERE / f'report.{lang}.md', {'results.json':
                           f"/api/v2/projects/{s.project}/artifacts/{artifacts['results']['artifact_id']}"}))
            p.note('execution:' + lang, 'E53 原设计与执行补充 / Design and amendments ' + lang,
                   render(HERE / f'design.{lang}.md') + '\n\n' + render(HERE / 'execution-notes.md'))
        image_key = 'image:summary'
        if image_key not in p.state:
            p.remember(image_key, p.image('E53 measured contrasts', WORK / 'summary.png'))
        p.document('record:figure', 'record', 'E53 结果图 / Measured contrasts', p.state[image_key])
        p.document('record:replay', 'record', 'E53 全海场景与实际声音 / Full habitat and actual signals',
                   f"[下载完整交互回放 / Download interactive replay](/api/v2/projects/{s.project}/artifacts/{artifacts['replay']['artifact_id']})\n\n"
                   "HTML下载后在浏览器打开，可切换分支、拖动模拟时间、查看双耳频带并截图。"
                   "画面是完整海洋的记录，不是重新生成的示意动画。\n\n"
                   "Open the downloaded HTML in a browser. Select a recorded world, seek, inspect ear bands, or save a screenshot. "
                   "Frames hold the observed physical state between 200 ms samples. Links show recorded environmental deliveries, "
                   "including signals experimentally muted before Core input. No fabricated trajectories or neural links.")
        p.document('record:measurements', 'record', 'E53 过程对照与结果 / Process contrasts and outcomes',
                   f"[机器可读结果 / Machine-readable results](/api/v2/projects/{s.project}/artifacts/{artifacts['results']['artifact_id']})\n\n"
                   "两种环境种子是两个重复来源；同一世界的分叉、个体及连续帧不冒充独立重复。"
                   "Two environment seeds, with matched full-world forks; not independent per-frame trials.")
        archive = archive_once(p, 'E53 embodied communication evidence.zip', historical_scope=(
            'Three original E38 candidate archives are included read-only as founders',
            'Complete new E53 worlds, stimuli, acoustic packets, trajectories and checkpoints are included',
            'Original Core dynamics, historical experiments and language adapters are unchanged'))
        p.document('record:evidence', 'record', 'E53 原始输入、状态与实验代码 / Complete evidence',
                   f"[证据包 / Evidence archive](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
                   "协议/1的身体感官在 inputs/，实际听觉另在 communication.jsonl.gz。"
                   "协议/2的 inputs/ 已含同次采样听觉；日志中的听觉为组成分量，不得重复投递。"
                   "一次零推进监控暂停及恢复目录均保留。\n\n"
                   "For /1, body inputs in inputs/ and auditory inputs in communication.jsonl.gz are separate submissions. "
                   "For /2, inputs/ already contains the joint body/ear stimulus: the logged auditory component must NOT be delivered twice. "
                   "The zero-advance monitoring pause and its resumed stage are both preserved.")
        # Read back only the small published reports, not the full evidence archive.
        for key in ('report:zh', 'report:en'):
            row = p.state[key]
            actual = research_documents.get(s.db, s.project, row['id'], revision=row['revision'])
            if actual['content_hash'] != row['content_hash']:
                raise RuntimeError('report publication mismatch')
        with s.db.tx() as tx:
            dbbytes = tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        resources = {'local_bytes': sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
                     'database_growth': max(0, dbbytes - s.meta['database_bytes_before']),
                     'usage': read_json(WORK / 'usage.json'),
                     'available_memory_bytes': psutil.virtual_memory().available,
                     'free_bytes': {d: shutil.disk_usage(d + ':/').free for d in ('C', 'E')}}
        p.document('record:delivery', 'record', 'E53 交付与资源 / Delivery and resources',
                   f"研究项目 / Project: `{s.project}`\n\n"
                   f"完成阶段 / Completed stages: {len(summary['cases'])}; "
                   f"recorded simulation compute: {summary['total_compute_seconds'] / 60:.2f} minutes.\n\n"
                   f"保留中断 / Preserved interruptions: {len(summary['interrupted_cases'])}.\n\n"
                   f"本地证据（含归档）/ Local including archive: {resources['local_bytes'] / 2**20:.1f} MiB.\n\n"
                   f"数据库增长 / Database growth: {resources['database_growth'] / 2**20:.1f} MiB; shared writes may contribute.\n\n"
                   f"共享账户 / Shared-account usage: 56% → {resources['usage']['used_percent']}%.\n\n"
                   "模拟预算未扩大；仅证据发布的本地原件＋ZIP＋数据库总上限另登记为6 GiB。"
                   "Simulation limits unchanged; publication-only combined source/ZIP/database ceiling amended to6 GiB.\n\n"
                   "No Core or default changes. No old data overwritten. No push or user-service operation.")
        delivery = {'project': s.project, 'archive': archive, 'artifacts': artifacts,
                    'documents': {k: v['id'] for k, v in p.state.items() if k.startswith(('report:', 'record:'))},
                    'resources': resources}
        if not (HERE / 'delivery.json').exists():
            write_json(HERE / 'delivery.json', delivery)
        print(json.dumps({'project': s.project,
                          'storage_MiB': (resources['local_bytes'] + resources['database_growth']) / 2**20}), flush=True)
    finally:
        s.db.close()


if __name__ == '__main__':
    main()
