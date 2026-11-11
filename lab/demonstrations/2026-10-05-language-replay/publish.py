"""Append replay/video artifacts to E52; never execute a consciousness or rewrite a report."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once

WORK = ROOT/'.work/language-replay-20261005'
HERE = Path(__file__).resolve().parent


def main():
    study = ArchivedStudy(ROOT/'.work/coadaptive-language-20261005')
    study.work = WORK  # A separate publication ledger; existing E52 records remain untouched.
    publication = Publication(study)
    try:
        replay = artifact_once(publication, 'teaching-replay-json', WORK/'language-replay.json',
            '教学回放 E50 + E52 · Teaching replay.json', 'application/json',
            metadata={'schema':'threemind.language-replay/1','duration_s':224,'sources':['E50','E52'],
                      'core_advanced':False,'answers_regenerated':False})
        video = artifact_once(publication, 'teaching-replay-mp4', WORK/'threemind-teaching-replay.mp4',
            'ThreeMind 教学与实际回答 · Teaching and actual answers.mp4', 'video/mp4',
            metadata={'schema':'threemind.language-replay-video/1','replay_artifact_id':replay['artifact_id'],
                      'duration_s':224,'width':1920,'height':1080,'fps':15,'audio':False})
        poster = artifact_once(publication, 'teaching-replay-poster', WORK/'poster.png',
            '教学回放封面 · Teaching replay.png', 'image/png',
            metadata={'replay_artifact_id':replay['artifact_id']})
        url = lambda a: f"/api/v2/projects/{study.project}/artifacts/{a['artifact_id']}"
        record = publication.document('teaching-replay-record-v1','record',
            '教学、命名与连接对照：可视化回放 / Teaching replay',
            f"3分44秒 / 3 min 44 s · 1920×1080 · 15 fps · 字幕，无音轨 / captions, no audio.\n\n"
            f"[视频 / Video]({url(video)}) · [回放数据 / Replay data]({url(replay)}) · [封面 / Poster]({url(poster)})\n\n"
            "在当前项目打开‘对话实验 → 教学回放与视频’，选择本回放；可播放、定位、截图与录屏。 / Open Dialogue experiments → Teaching replay & video in this project.\n\n"
            "E50教学和独立复测、E52现场问答分章展示。实际回答来自已存证据，无重新推理。E50部分测试仅展示物体，没有文字提问；E52错答及教师纠正原样保留。 / E50 teaching and independent probes are separated from E52 live dialogue. Answers are recorded outputs, not new inference. E50 visual-only tests contain no text question; E52 errors and teacher corrections remain visible.\n\n"
            "场景按原定义示意重建，原视觉是五条射线的距离和RGB。节点布局不表示脑区；采样间保持原值，教师纠正后没有记录的活动不补画。 / The scene is illustrative; original vision consists of five ray distances and RGB values. Display positions are not brain regions; recorded samples are held, and unrecorded post-correction activity is not invented.\n\n"
            "这是演示工具交付，不是新的实验或新结论；E50/E52原报告、数据、内核和默认参数保持不变。 / This is a visualization delivery, not a new experiment or conclusion; original reports, evidence, Core and defaults remain intact.")
        delivery={'project':study.project,'replay':replay,'video':video,'poster':poster,
                  'record':str(record['id']),'ui_route':f"/dialogue/replay?artifact={replay['artifact_id']}"}
        (HERE/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(delivery,ensure_ascii=False))
    finally:
        study.db.close()


if __name__=='__main__':
    main()
