"""Pack every completed E63 record, keeping the stopped sampling separate."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.active_vision_replay import pack
WORK=ROOT/'.work/rehearsal-centered-20261007'
cases=[p for p in (WORK/'cases').iterdir() if (p/'result.json').exists() and (p/'process.jsonl.gz').exists()]
cases.sort(key=lambda p:json.loads((p/'started.json').read_bytes())['epoch'])
labels={'centered-teaching':'中央物体 · 初始104课', 'centered-normal':'中央物体 · 首次32题',
    'centered-correction':'中央物体 · 普通纠错与旧例复习','centered-corrected-normal':'中央物体 · 纠错后32题',
    'centered-variant-normal':'中央物体 · 未纠错来源做相同后测'}
for key,name in [('recent','最近缓存'),('reservoir','随机保留旧例'),('representative','旧代表＋近期')]:
    labels['rehearsal-'+key]=name+' · 完整补课'
    labels['motor-'+key+'-normal']=name+' · 12次实际眼手测试'
data=pack([p/'process.jsonl.gz' for p in cases],'ThreeMind · E63完整复习与认识记录',labels)
template=(ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
with (WORK/'rehearsal-centered.html').open('x',encoding='utf-8') as f:f.write(template.replace('__DATA__',payload))
print(json.dumps(dict(clips=len(data['clips']),frames=sum(len(c['frames']) for c in data['clips']))))
