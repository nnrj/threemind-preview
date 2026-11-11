from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    p=ROOT/path;old=p.read_text(encoding='utf-8')
    if text.strip() not in old:p.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


for lang in ('zh','en'):
    zh=lang=='zh'
    summary=('E50完成：局部过程已教共同所指74/80；相关连接屏蔽16→8，匹配16，救援16，目标移植6/16随供体改变。全新对应两冻结头均0/40，不能称通用新经历翻译。局部优先的可变节点表达器及CLI已验，旧器/Core/default保留。输出总线观察帧与实际传输有差别，后者对照尚未执行。用户批准下一步先教可感知时钟与复述句式，再判时间概念；不把后期读出漂移混同“昨天”教学。' if zh else
        'E50 complete: taught common referents74/80 from local processes; targeted silencing16→8, matched16, rescue16; targeted transfer6/16 follows donor. Both frozen readers score0/40 on entirely new assignments, so general new-experience translation is not established. Variable-node local-first Python/CLI accepted; old tools/Core/defaults preserved. Observation frames differ from actual transmissions; that comparison is pending. Clock and retelling teaching is authorized next, distinct from reader drift.')
    path=ROOT/f'docs/{lang}/plans/research-backlog.md';text=path.read_text(encoding='utf-8')
    marker='<!-- research-plan-current:start -->'
    if summary not in text:text=text.replace(marker,marker+'\n\n**'+summary+'**',1)
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R17 /'):
            lines[i]=('| R17 / E50完成，继续 | 局部活动表达、共同所指与回答归属 | 74/80；选择性屏蔽/救援与部分供体名字转移；全新对应0/40 | 下一步时间教学另见R32；新对应与自主表达仍待定位 | [E50](../../../lab/explorations/2026-10-05-graph-expression/report.zh.md) |' if zh else
                '| R17 / E50 complete, continuing | Local expression and attribution |74/80; selective silence/rescue and partial donor naming; unseen assignments0/40 | Clock teaching inR32; new correspondence and voluntary expression remain open | [E50](../../../lab/explorations/2026-10-05-graph-expression/report.en.md) |')
        if line.startswith('| T07 /'):
            lines[i]=('| T07 / 本期工具完成，继续 | 双向外设与局部过程表达 | 局部优先、变化通道、继续训练、CPU/CUDA、旧检查点及CLI已验 | [工具](../reference/graph-expression.md)；真实传输流对照及生产聊天接入未完成 |' if zh else
                '| T07 / tools delivered, continuing | Peripheral and local process expression | Local-first variable channels, continued training, CPU/CUDA, old checkpoints and CLI accepted | [Tool](../reference/graph-expression.md); actual transmission comparison and production chat remain open |')
    text='\n'.join(lines)+'\n'
    c=('| C28 | E50局部表达与回答归属 |384来源/探针、8模型；74/80，局部干预及移植定位部分回答；新对应未通过，Core未改 | [报告](../../../lab/explorations/2026-10-05-graph-expression/report.zh.md) |' if zh else
       '| C28 | E50 local expression and attribution |384cases,8models;74/80, selective controls and transfers; unseen assignments fail; Core unchanged | [Report](../../../lab/explorations/2026-10-05-graph-expression/report.en.md) |')
    if '| C28 |' not in text:
        rows=text.splitlines();index=next(i for i,r in enumerate(rows) if r.startswith('| C27 |'));rows.insert(index+1,c);text='\n'.join(rows)+'\n'
    r=('| R32 / P1 已批准 | 时钟、时间词与经历复述 | E50未教“昨天”；不能混同表达漂移 | 可感知钟/场景/教师句式，当前相同而过去不同，钟速/起点及无学习对照 | [方案](clock-grounded-recollection.md) |' if zh else
       '| R32 / P1 authorized | Clocks, temporal words and recollection | E50 did not teach yesterday; distinct from reader drift | Perceptible clock, scenes, sentence teaching, identical present/different past, clock-rate/origin and no-learning controls | [Plan](clock-grounded-recollection.md) |')
    if '| R32 /' not in text:
        rows=text.splitlines();index=next(i for i,r in enumerate(rows) if r.startswith('| R31 /'));rows.insert(index+1,r);text='\n'.join(rows)+'\n'
    path.write_text(text,encoding='utf-8')
    report=f'../../../lab/explorations/2026-10-05-graph-expression/report.{lang}.md'
    append(f'docs/{lang}/plans/research-backlog.md',f'### 2026-10-05：E50完成 / completion\n\n{summary}\n\n[Report]({report})')
    body=(summary+' 初始全图工具欠拟合，用户要求局部优先后主路改为六个活动字段；两个外设版本及失败均保留。不能将联合工具修订归于局部性一个原因。时钟设想及原话单列，尚不宣称已会复述昨天。' if zh else
          summary+' Initial whole-graph underfitting and both reader versions are retained. The user requested local-first expression, now six dynamic fields. Joint instrument changes do not isolate locality as a sole cause. Clock teaching and the original clarification are separately recorded, not a claim of yesterday recall.')
    for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
        append(f'docs/{lang}/history/{name}',f'### 2026-10-05：E50局部表达与时间教学 / Local expression and clock teaching\n\n{body}\n\n[报告 / Report](../../../../lab/explorations/2026-10-05-graph-expression/report.{lang}.md) · [原话与时间计划 / Clock clarification](../../plans/clock-grounded-recollection.md)')
    append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — {summary} [E50](../../../lab/explorations/2026-10-05-graph-expression/report.{lang}.md)')
    append(f'docs/{lang}/plans/index.md','- [时钟教学与经历复述 / Clock-grounded recollection](clock-grounded-recollection.md)')
    append(f'docs/{lang}/plans/graph-process-expression.md',f'## 2026-10-05：本轮完成 / Completion\n\n{summary}\n\n[报告 / Report]({report})')
append('docs/zh/history/classical/shiji-05.md','### 察局部之流变\n\n新译器先读全图，初不善，改而能习。用户戒以全图代言，遂取参与之局部流变。已教之物，八十问中得七十四；闭相关之边，十六答减为八，复之则复。移其经历之边，十六中六随供体改名。然四种新配俱未能译，故记其能与未能，旧器旧据不废。又议钟表与往事：先教计时与述事之辞，乃可问刚刚与昨日；不可混译器随变之失与未教之问。')
append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：局部译读既验，另议钟教\n\nE50毕，三百八十四案，八器。局部所指多可读，选择性闭边、复边与移边有别；新配未通。核未改。核查输出总线，知观察帧非尽为实发之信号，留待后试。用户谓不教时钟，不可责其不识昨日，遂另立钟教与述事之案。')
