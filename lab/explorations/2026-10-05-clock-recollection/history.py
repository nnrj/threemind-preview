from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,body):
    p=ROOT/path;t=p.read_text(encoding='utf-8')
    if body.strip() not in t:p.write_text(t.rstrip()+'\n\n'+body.strip()+'\n',encoding='utf-8')


for lang in ('zh','en'):
    zh=lang=='zh'
    summary=('E51有限试验完成：教可感知钟与现在/刚刚句式，144轮/652模拟秒；钟面4/4、时间词前缀24/24，但物体内容当前3/12、刚刚2/12。外设训练仅12/36，按33/36事前门槛停止第二来源及长尺度。24/24不同前情的实际局部输入仍有差异；学习组差异幅度高于无学习组范围，尚未成为可靠复述。Core/default/旧编码不改；本批语言呈现20ms间隔已登记。小时/昨天未验证。' if zh else
        'E51 bounded pilot complete:144episodes/652simulated seconds with perceptible clock and now/just-now teaching. Clock4/4 and prefixes24/24, but current object3/12 and past2/12. External fit12/36misses the preregistered33/36gate; second source and longer periods stopped. All24past-context comparisons retain different local inputs; learned differences exceed the no-learning range but are not reliably recounted. Core/defaults/encoder unchanged;20mslanguage presentation recorded. Hours/yesterday untested.')
    path=ROOT/f'docs/{lang}/plans/research-backlog.md';t=path.read_text(encoding='utf-8');marker='<!-- research-plan-current:start -->'
    if summary not in t:t=t.replace(marker,marker+'\n\n**'+summary+'**',1)
    lines=t.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R32 /'):
            lines[i]=('| R32 / E51有限完成，后续待定 | 时钟与经历复述 | 钟4/4；前情影响保留且被学习放大；物体复述未过，外设12/36欠拟合 | 先使已教短时经历可靠表达，再延长周期及选择性归因；不判已会昨天 | [E51](../../../lab/explorations/2026-10-05-clock-recollection/report.zh.md) |' if zh else
                '| R32 / E51 pilot complete, follow-up open | Clock and recollection | Clock4/4; learning amplifies retained past influence; retelling fails, external fit12/36 | First reliable short taught-event expression, then longer periods and selective attribution | [E51](../../../lab/explorations/2026-10-05-clock-recollection/report.en.md) |')
    if not any(r.startswith('| C29 |') for r in lines):
        i=next(i for i,r in enumerate(lines) if r.startswith('| C28 |'))
        lines.insert(i+1,('| C29 | E51时钟教学与短时复述 |114来源/探针，1模型；钟面与句式可读，经历内容未可靠译出；按门槛停止扩大 | [报告](../../../lab/explorations/2026-10-05-clock-recollection/report.zh.md) |' if zh else
            '| C29 | E51 clock and brief-event retelling |114cases,1model; clock/prefix readable, content unreliable; expansion stopped at registered gate | [Report](../../../lab/explorations/2026-10-05-clock-recollection/report.en.md) |'))
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    append(f'docs/{lang}/plans/research-backlog.md',f'### 2026-10-05：E51完成 / pilot completion\n\n{summary}\n\n[报告 / Report](../../../lab/explorations/2026-10-05-clock-recollection/report.{lang}.md)')
    for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
        append(f'docs/{lang}/history/{name}',f'### 2026-10-05：可感知钟与往事表达 / Clock and recollection\n\n{summary}\n\n[登记 / Registration](../../../../lab/explorations/2026-10-05-clock-recollection/design.{lang}.md) · [报告 / Report](../../../../lab/explorations/2026-10-05-clock-recollection/report.{lang}.md)')
    append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — {summary} [E51](../../../lab/explorations/2026-10-05-clock-recollection/report.{lang}.md)')
    plan=ROOT/f'docs/{lang}/plans/clock-grounded-recollection.md';t=plan.read_text(encoding='utf-8')
    if zh:
        t=t.replace('- 当前：方案与原话已登记；尚未开始该新批次，不把 E50 的 440／500 秒测量当作时间概念实验。',
            '- 当前：E51短尺度试验已完成；钟面与句式可读，物体复述不可靠。外设欠拟合触发事前停止门槛，尚未教小时/昨天。E50的440/500秒读出漂移仍属另一问题。')
    else:
        t=t.replace('- Current: proposal and clarification registered; not yet executed. E50 measurements at 440/500 seconds are not temporal-concept tests.',
            '- Current: E51 short-scale pilot complete; clock/prefix reading works, object retelling does not. External underfitting triggered the registered stop; hours/yesterday remain untaught. E50 reader drift at440/500s remains a different question.')
    plan.write_text(t,encoding='utf-8')
    append(f'docs/{lang}/plans/clock-grounded-recollection.md',f'## 2026-10-05：执行结果 / Outcome\n\n{summary}\n\n[报告 / Report](../../../lab/explorations/2026-10-05-clock-recollection/report.{lang}.md)')
append('docs/zh/history/classical/shiji-05.md','### 教钟而问往事\n\n既议先教而后问，乃置旋针于境，以光量入感官，不以答案入核。教今昔之辞，一百四十四轮。钟面四问皆中，今昔答辞亦分，然所见之物多误。三十六习例仅十二可译，未及预定之关，遂止扩展。又验同今异昔，局部流变皆有别，学者之别大于未学者；故不可谓往事无迹，亦不可谓已能述往事。小时与昨日留待后试。')
append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：时钟短试有迹而未善述\n\nE51行一百一十四案。钟为外设，语言逐时而至，核仍其旧。钟面可名，今昔可成辞，而物名多错；以译器习例未过关，止第二来源及长时之试。同今异昔之迹二十四对俱异，学习使其影响加深，然不得以有迹便称善忆善言。')
