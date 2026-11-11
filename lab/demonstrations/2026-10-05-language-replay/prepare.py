"""Package existing E50/E52 evidence for the UI. Does not instantiate or advance Core."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'.work/language-replay-20261005'
FIRST = ROOT/'.work/graph-expression-20261005'
E50 = ROOT/'.work/graph-expression-v2-20261005'
E52 = ROOT/'.work/coadaptive-language-20261005'
OBJECTS = [dict(name=n, shape=s, color=c, position=p) for n,s,c,p in (
    ('红球','sphere','#ea5851',[-.6,-.6]), ('蓝盒','box','#5889e8',[.6,-.6]),
    ('绿柱','cylinder','#55b77b',[-.6,.6]), ('黄块','block','#e5b748',[.6,.6]))]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def zipped(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT)).replace('\\','/')


def process(path):
    raw = zipped(path)
    identities = {}
    frames = []
    for f in raw['trajectory']:
        nodes = []
        for n in f['nodes']:
            identities[str(n['id'])] = int(n['channel'])
            nodes.append([int(n['id']), n['activation'], n['inhibition'], n['associative']])
        frames.append({'t': int(f['time_us'])/1e6, 'nodes': nodes})
    edges = []
    for state in raw.get('states', []):
        rows = sorted(state['edges'], key=lambda e: ((int(e['source'])*2654435761 ^ int(e['target'])*2246822519) & 0xffffffff))
        edges.append({'t': int(state['time_us'])/1e6, 'total': len(rows),
            'rows': [[int(e['source']),int(e['target']),e['weight']] for e in rows[:300]]})
    return {'frames': frames, 'nodes': identities, 'edges': edges,
            'from': int(raw['start_us'])/1e6, 'to': int(raw['end_us'])/1e6,
            'evidence': [relative(path)], 'sampling': '节点20ms；连边仅在已存快照更新；采样间保持原值'}


def card(key, title, text, duration, stats):
    return {'id':key,'title':title,'subtitle':'ThreeMind · 教学与回答的实验回放',
        'caption':text,'duration':duration,'kind':'card','stats':stats,'source':'E50 / E52 · 原始证据的可视化',
        'objects':OBJECTS,'events':[],'frames':[],'nodes':{},'edges':[],'evidence':[],'from':0,'to':0}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'language-replay.json'
    if output.exists():
        raise RuntimeError('Use a new output folder; the prepared replay is not overwritten')
    clips = [card('intro','当经历变成回答',
        '看它接受教学、形成响应，再看内部连接怎样参与回答。\n画面来自已完成实验；旁白文字为说明，回答取自原始记录。',12,
        [{'value':'74 / 80','label':'E50早期已教命名'}, {'value':'16 → 8 → 16','label':'相关通路屏蔽与恢复'}])]
    parent = FIRST/'cases/s223-multi-continued'
    with gzip.open(parent/'teaching-440.jsonl.gz','rt',encoding='utf-8') as f:
        teaching = [json.loads(line) for line in f]
    for key, start, end, duration, title, caption in (
        ('teach-first',0,72,30,'先反复教，再间隔复习','每一种句式初次连续12遍。名字与物体同时被感官观测。\n正在回放来源223的实际教学；此阶段没有记录表达器回答。'),
        ('teach-spaced',72,440,26,'让经历留下来','随后以2、4、8、16模拟秒间隔复习，共192次教学。\n期间物理遥测背景持续存在；这里只加速播放，不改变实验时间。')):
        frames = [r for r in teaching if 'nodes' in r and start <= int(r['time_us'])/1e6 <= end]
        ids = {str(n['id']): int(n['channel']) for r in frames for n in r['nodes']}
        events = [{'at':(r['lesson']['seconds']-start)/(end-start)*duration,
                   'role':'teacher','label':'教师 · 原始教学输入','text':r['lesson']['text'],
                   'item':r['lesson']['item'],'repeat':r['lesson']['repetition']+1,
                   'measurement':r['measurement']} for r in teaching if 'lesson' in r and start <= r['lesson']['seconds'] < end]
        clips.append({'id':key,'title':title,'subtitle':'E50 · 来源223 · 原教学历史','caption':caption,
            'duration':duration,'kind':'teaching','source':'E50 · continuous-memory/2 · 原始教学记录',
            'objects':OBJECTS,'events':events,'nodes':ids,'edges':[],
            'frames':[{'t':int(r['time_us'])/1e6,'nodes':[[int(n['id']),n['activation'],n['inhibition'],n['associative']] for n in r['nodes']]} for r in frames],
            'evidence':[relative(parent/'teaching-440.jsonl.gz'),relative(parent/'definition.json')],
            'from':start,'to':end,'sampling':'教学节点每0.5模拟秒记录；未保存期间连边，不补画连接',
            'stats':[{'value':'192次','label':'完整课程总量'},{'value':'12遍','label':'每句首次重复'}]})
    model = read(E50/'models/multi-s223-local.json')
    def probe_row(item, condition='continued'):
        return next(r for r in model['rows'] if r['condition']==condition and r['seconds']==440
                    and r['item']==item and r['perspective']=='visual' and r['view']==9)
    def test_clip(key, row, caption, source=None, duration=10):
        data = process(Path(row['evidence']))
        item = row['item']
        return data | {'id':key,'title':'换个角度，它仍能说出名字' if not source else source,
            'subtitle':f"E50 · 来源223 · {'原教学' if row['condition']=='continued' else '反向教学'} · 同快照独立测试副本",
            'source':'E50 · 冻结同一个体的局部表达器 · 测试未给目标名字',
            'duration':duration,'kind':'probe','objects':OBJECTS,'item':item,'motionSeconds':8,
            'caption':caption,'expected':row['target'],'output':row['output'],
            'events':[{'at':0,'role':'input','label':'测试输入 · 仅视觉','text':f'展示{OBJECTS[item]["name"]}（没有文字提问）','item':item},
                      {'at':8,'role':'answer','label':'表达器 · 本次观察窗口的实际输出','text':row['output']}],
            'stats':[{'value':'2秒','label':'原始观察窗口'},{'value':'20ms','label':'节点采样间隔'}]}
    for item in range(4):
        row = probe_row(item)
        assert row['output']==row['target']
        clips.append(test_clip(f'name-{item}',row,
            '这里的“提问”是展示物体，输入里没有答案名字。\n四个示例均来自同一来源；完整早期命名结果为74/80。'))
    row = probe_row(0,'reversal')
    clips.append(test_clip('reversal',row,
        '眼前仍是红球，另一套教学却给它取了不同名字。\n同来源表达器读出了“戊”；此段来自另一教学历史，非原个体突然改口。',
        source='同一个物体，不同经历，不同名字',duration=12))
    clips.append(card('intervention-intro','回答与内部连接有关吗？',
        '固定表达器，用同一时刻的意识快照建立独立副本。\n比较正常、相关连接屏蔽、其他连接屏蔽与恢复；每次都展示同一红球。',10,
        [{'value':'16 / 16','label':'正常与其他连接屏蔽'},{'value':'8 / 16','label':'相关连接屏蔽'},{'value':'16 / 16','label':'相关连接恢复'}]))
    baseline = test_clip('control-base',probe_row(0),'同快照副本：正常状态。\n同一个已冻结表达器，实际输出“甲”。',source='对照一 · 正常连接')
    clips.append(baseline)
    records = read(E50/'attribution-s223.json')['rows']
    for kind,title,caption in (
        ('silence-target','对照二 · 屏蔽视觉—语言相关连接','此副本的相关连接被暂时屏蔽，实际回答变为“戊”。\n图中连边仍表示结构；屏蔽是实验条件，未把结构删除。'),
        ('silence-matched','对照三 · 屏蔽其他匹配连接','换为其他数量相近的连接，实际回答仍是“甲”。\n匹配并非完全相同的拓扑和功能；详见原报告。'),
        ('rescue','对照四 · 解除相关连接屏蔽','同快照的恢复副本，实际回答重新成为“甲”。\n这些对照支持：部分回答依赖内部连接，而不只是在外围认图。')):
        row = next(r for r in records if r['condition']=='continued' and r['intervention']==kind and r['item']==0)
        clip = test_clip(kind,row,caption,source=title)
        clip['intervention']=kind
        clip['evidence'].append(relative(E50/'attribution-s223.json'))
        clips.append(clip)
    clips.append(card('e52-intro','下一步：边学，边回答，听见自己',
        '下面切换到E52另一批实验：有真实文字提问，也有教师纠正。\n这是不同课程、不同表达器；不要与刚才的E50拼成一次连续实验。',10,
        [{'value':'24 / 80','label':'E52共同学习问答'},{'value':'进行中','label':'可靠的新经历翻译'}]))
    source = E52/'cases/s223-feedback-stage0'
    with gzip.open(source/'dialogue.jsonl.gz','rt',encoding='utf-8') as f:
        dialogues=[json.loads(line) for line in f]
    new_objects=[dict(o) for o in OBJECTS]
    new_objects[1].update(name='蓝球',shape='sphere')
    new_objects[2].update(name='红盒',shape='box',color='#ea5851')
    new_objects[3].update(name='蓝盒',shape='box',color='#5889e8')
    for index in (4,6):
        row=dialogues[index]
        data=process(source/f'teaching-observation-{index}.json.gz')
        clips.append(data|{'id':f'e52-{index}','title':'实际问答：回答之后，教师继续示范',
            'subtitle':f'E52 · 来源223 · 阶段0 · 第{index+1}轮现场问答',
            'source':'E52 · 现场回答，不是训练完成后重读旧样本',
            'caption':'真实输出会经原感官返回，随后教师给出正常语言示范。\n这次红球答错、蓝球答对；仅展示事实，尚未把纠正稳定学会。',
            'duration':14,'kind':'probe','objects':new_objects,'item':row['item'],'motionSeconds':8,
            'expected':row['target_external_only'],'output':row['answer']['text'],
            'events':[{'at':0,'role':'input','label':'教师提问 · 原话','text':row['question']['text'],'item':row['item'],'measurement':row['question']['measurement']},
                      {'at':8,'role':'answer','label':'表达器 · 当时实际输出','text':row['answer']['text']},
                      {'at':10,'role':'teacher','label':'随后教师示范 · 原话','text':row['teacher']['text']}],
            'evidence':data['evidence']+[relative(source/'dialogue.jsonl.gz')],
            'stats':[{'value':'原话自听','label':'实际回答进入感官'},{'value':'独立分期','label':'每4轮更新外设'}]})
    clips.append(card('ending','已经能读出一些经历，继续打通表达',
        '已教物体的名字能够从内部活动中读出，相关连接对部分回答有作用。\n新经历如何可靠表达，仍是下一步；这段录像展示的是实际走到的位置。',16,
        [{'value':'74 / 80','label':'已教物体的早期命名'},{'value':'恢复有效','label':'相关连接参与输出'},{'value':'继续研究','label':'新经历与自然语言'}]))
    pack={'schema':'threemind.language-replay/1','title':'当经历变成回答 · ThreeMind 教学回放',
        'description':'E50教学、命名和连接对照；E52现场提问与教师示范。原始记录回放，不运行意识内核。',
        'created_on':'2026-10-05','width':1920,'height':1080,'clips':clips,
        'provenance':{'core_advanced':False,'answer_regenerated':False,'interpolation':False,
            'world':'根据原场景定义作示意重建；原视觉是五条射线的距离和RGB，不是完整摄影画面',
            'graph':'匿名通道确定性布局；位置不是脑区；绘图连边最多300条的固定抽样，不改变模型',
            'sources':['lab/explorations/2026-10-05-graph-expression/report.zh.md','lab/explorations/2026-10-05-coadaptive-language/report.zh.md']}}
    output.write_text(json.dumps(pack,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    position=0
    chapters=[]
    for clip in clips:
        chapters.append({'id':clip['id'],'title':clip['title'],'start_s':position,'duration_s':clip['duration'],'source':clip['source']})
        position+=clip['duration']
    manifest={'file':str(output),'clips':len(clips),'duration_s':position,'chapters':chapters,
        'bytes':output.stat().st_size,'sources':sorted({p for c in clips for p in c['evidence']} | {relative(E50/'models/multi-s223-local.json')}),
        'core_advanced':False,'answers_regenerated':False}
    (Path(__file__).parent/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print({k:v for k,v in manifest.items() if k!='sources'})


if __name__=='__main__':
    main()
