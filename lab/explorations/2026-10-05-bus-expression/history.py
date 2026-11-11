"""Dated bilingual registration, preserving all previous reports."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def append(path,body):
    p=ROOT/path;text=p.read_text(encoding='utf-8')
    if body.strip() not in text:p.write_text(text.rstrip()+'\n\n'+body.strip()+'\n',encoding='utf-8')
for lang in ('zh','en'):
    title='E49：总线与表达器校准' if lang=='zh' else 'E49: buses and expression calibration'
    text=('用户明确允许外设教学标记，交互不得夹带答案；要求核查输入/输出总线，先校准表达再判内核能力。登记E49：保持原值与旧核，分离传输、观察压缩、数值训练，重用E47/E48资料；优先查明工具是否能学会已有对应，合格后再验新经历。共同发育是候选，不把Transformer自身学习归给Core。' if lang=='zh' else
          'The user permits external training labels but no hidden answers in interaction. E49 audits input/output buses and separates transport, lossy observation and numerical learning. Reuse raw E47/E48 evidence with unchanged Core; calibrate existing correspondences before unseen experience. Joint development remains a candidate, and adapter learning is not attributed to Core.')
    for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
        append(f'docs/{lang}/history/{name}',f'### 2026-10-05：{title}\n\n{text}\n\n[E49](../../plans/bus-and-expression-calibration.md)')
    append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — {title}。[E49](../plans/bus-and-expression-calibration.md)')
    append(f'docs/{lang}/plans/index.md',f'- [{title}](bus-and-expression-calibration.md)')
    p=ROOT/f'docs/{lang}/plans/research-backlog.md';old=p.read_text(encoding='utf-8');lines=old.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R17 /'):
            lines[i]=('| R17 / E49执行中 | 总线、原始表达和关系迁移 | E48工具欠拟合，旧核保持 | 先检查总线/压缩/训练，再冻结验新经历 | [E49](bus-and-expression-calibration.md) |' if lang=='zh' else
                      '| R17 / E49 active | Buses, raw expression and relation transfer | E48 calibration incomplete; Core retained | Audit transport/compression/training before frozen new-experience tests | [E49](bus-and-expression-calibration.md) |')
    p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    append(f'docs/{lang}/plans/research-backlog.md',f'### 2026-10-05：{title}\n\n{text}\n\n[E49](bus-and-expression-calibration.md)')
append('docs/zh/history/classical/shiji-05.md','### 审总线而校译器\n\n用户谓教译器可有名，入意识不可暗示其解。又疑总线有遗失，遂议E49，分传输、取样与译器之学，原迹不损，旧核不更。先使器能译所习，乃论新事之通。')
append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：审视输入输出\n\n定E49，察总线有无失真，辨压缩与传递。教师可示译名，试时不可予答案；核外之学与核中之变，各明其属。')
