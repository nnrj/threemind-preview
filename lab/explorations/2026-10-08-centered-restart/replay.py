"""All complete teaching/question clips, not a selected highlight reel."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.active_vision_replay import pack
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/centered-restart-20261008'

cases=['blank-teaching','first-calibration','first-practice','exposure','later-calibration',
       'test-normal','confirmation-normal','test-silence','test-rescue']
paths=[WORK/'cases'/c/'process.jsonl.gz' for c in cases if (WORK/'cases'/c/'result.json').exists()]
labels={'blank-teaching':'从空白开始 · 完整104课与复习间隔','first-calibration':'外设校准 · 48次真实提问',
    'first-practice':'12项练习 · 全部回答','exposure':'再观察与间隔 · 无正确答案输入',
    'later-calibration':'外设校准 · 后12次提问','test-normal':'正式测试 · 全部32题',
    'confirmation-normal':'换位置与顺序确认 · 全部32题','test-silence':'固定表达器 · 屏蔽已有连接',
    'test-rescue':'固定表达器 · 解除屏蔽'}
data=pack(paths,'ThreeMind · 空白意识中央形色问答',labels)
template=(ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
with (WORK/'centered-restart.html').open('x',encoding='utf-8') as f:f.write(template.replace('__DATA__',payload))
print(json.dumps(dict(clips=len(data['clips']),frames=sum(len(c['frames']) for c in data['clips']))))
