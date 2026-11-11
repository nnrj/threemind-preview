"""Pack every completed E65 teaching and question frame; never run Core."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.active_vision_replay import pack
from lab.tools.service_study import new_json

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/centered-learning-20261008'
labels = {'baseline':'训练前 · 全部36题', 'teaching':'集中示范与旧例复习 · 全部89课和间隔',
          'new-calibration':'外设续校材料 · 全部48次无答案提问',
          'primary':'训练后主测 · 全部36题', 'confirmation':'新位置确认 · 全部36题'}
paths = [WORK/f'cases/{name}/process.jsonl.gz' for name in labels]
if any(not (p.parent/'result.json').exists() for p in paths): raise RuntimeError('complete stages required')
data = pack(paths,'ThreeMind · E65 中央形色续学与实际回答',labels)
template = (ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
payload = json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
output = WORK/'centered-learning.html'
with output.open('x',encoding='utf-8') as f: f.write(template.replace('__DATA__',payload))
result = dict(clips=len(data['clips']),frames=sum(len(c['frames']) for c in data['clips']),bytes=output.stat().st_size,
              by_case={name:dict(clips=sum(c['case']==name for c in data['clips']),
                     frames=sum(len(c['frames']) for c in data['clips'] if c['case']==name)) for name in labels})
new_json(HERE/'replay-manifest.json',result)
print(json.dumps(result))
