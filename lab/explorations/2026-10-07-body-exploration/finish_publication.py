"""Record E61 delivery using small manifests and artifact metadata, not a full reread."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from threemind_lab import research_documents
from threemind_lab.config import Settings

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/body-exploration-20261007'


def main():
    endpoint=urlsplit(Settings.from_env().database_url)
    if (endpoint.scheme,endpoint.hostname,endpoint.port,endpoint.path)!=('postgresql','127.0.0.1',5433,'/threemind'):
        raise ValueError('local database only')
    d=json.loads((HERE/'delivery.json').read_text(encoding='utf-8'))
    m=json.loads((WORK/'streamed-archive-manifest.json').read_text(encoding='utf-8'))
    refs=json.loads((WORK/'replay-artifacts.json').read_text(encoding='utf-8'))
    members={x['path'] for x in m['files']}
    processes={p.relative_to(WORK).as_posix() for p in (WORK/'cases').glob('*/process.jsonl.gz')}
    if len(processes)!=47 or not processes<=members:
        raise ValueError('original process missing from archive manifest')
    if len(refs['chapters'])!=47 or any(d['artifacts'][k]!=v for k,v in refs['chapters'].items()):
        raise ValueError('replay references differ')
    if len(members)!=d['archive']['members'] or m['bytes']!=d['archive']['bytes']:
        raise ValueError('archive manifest differs')
    study=ArchivedStudy(WORK);pub=Publication(study)
    try:
        with study.db.tx(study.project) as tx:
            a=tx.execute('SELECT bytes, sha256 FROM artifacts WHERE id=%s AND project_id=%s',
                         (d['archive']['artifact_id'],study.project)).fetchone()
        if not a or a['bytes']!=d['archive']['bytes'] or a['sha256']!=d['archive']['sha256']:
            raise ValueError('stored artifact metadata mismatch')
        total=(d['local_bytes']+d['database_growth_bytes'])/2**30
        for lang in ('zh','en'):
            report=next(r['id'] for r in d['reports'] if r['language']==lang)
            archive=f'/api/v2/projects/{study.project}/artifacts/{d["archive"]["artifact_id"]}'
            replay=f'/api/v2/projects/{study.project}/artifacts/{d["artifacts"]["body-exploration.html"]["artifact_id"]}'
            body=(f'# E61交付完成：连续性更正已入库\n\n54阶段模拟已结束；未追加新的模拟。中英文更正报告已回读核对，旧8项目另增16条补注，不覆盖旧报告。完整系统重试尚未执行。\n\n- 47章、571段、85,760帧：[回放]({replay})。\n- 原始证据归档：[下载]({archive})，{d["archive"]["bytes"]:,}字节，733个文件。47份原过程均在归档内；派生HTML另作平台工件，不再重复装入ZIP，工件引用及重建代码保留。\n- 本地{d["local_bytes"]/2**30:.3f}GiB，数据库净增{d["database_growth_bytes"]/2**30:.3f}GiB，合计{total:.3f}GiB，低于8GiB上限。数据库增长保守包含同期间其他写入。\n- 检查上传返回大小、归档清单及数据库工件元数据；没有再次读取整包或逐个重哈希。浏览器播放、实际录制和窄屏视觉验收仍未完成。\n- 中文/英文报告身份：`{report}`；项目：`{study.project}`。\n\n下一期先保留E56工作基线、修复整个系统的连续保存和学习，再试单眼改进。Core动力学与旧证据未改。'
                  if lang=='zh' else
                  f'# E61 delivery complete: continuity correction published\n\nAll 54 simulation stages are closed, with no additional simulation. Bilingual corrected reports were read back; 16 separate scope notices were appended to eight old projects without replacing reports. Integrated reruns remain pending.\n\n- 47 chapters, 571 clips, 85,760 frames: [replay]({replay}).\n- [Original evidence]({archive}): {d["archive"]["bytes"]:,} bytes, 733 members. All 47 original process records are included. Derived HTML chapters are separate platform artifacts rather than duplicate ZIP entries; references and reconstruction code remain.\n- Local {d["local_bytes"]/2**30:.3f} GiB, net database growth {d["database_growth_bytes"]/2**30:.3f} GiB, total {total:.3f} GiB below the 8 GiB ceiling. Database growth conservatively includes any concurrent writes.\n- Checked upload size, small manifests and artifact metadata; no full archive reread or repeated hashing. Browser playback, recording and narrow-screen QA remain unverified.\n- Report ID: `{report}`; project: `{study.project}`.\n\nNext preserve the E56 working reference, repair complete-system persistence/learning, then test whole-eye changes. Core dynamics and old evidence were not changed.')
            path=HERE/f'delivery-summary.{lang}.md'
            if not path.exists():path.write_text(body+'\n',encoding='utf-8')
            saved=pub.document('record:final-delivery:'+lang,'record','E61 交付与连续性重试范围 / Delivery and rerun scope '+lang,body)
            got=research_documents.get(study.db,study.project,saved['id'])
            if got['spec']['blocks'][0]['markdown']!=body:raise ValueError('delivery record mismatch')
        pub.guard(reserve=1)
        print(json.dumps({'original_processes_in_archive':len(processes),'replay_artifacts':len(refs['chapters']),
                          'archive_members':len(members),'combined_GiB':total,'database_metadata_matches':True}))
    finally:study.db.close()


if __name__=='__main__':main()
