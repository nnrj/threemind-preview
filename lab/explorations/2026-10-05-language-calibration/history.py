"""Append approved calibration and composition decisions; no historical rewrites."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    file=ROOT/path
    previous=file.read_text(encoding='utf-8')
    if text.strip() not in previous:
        file.write_text(previous.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


def main():
    for lang in ('zh','en'):
        title='2026-10-05：先校感官，次调参数，再验组合' if lang=='zh' else '2026-10-05: calibrate senses, parameters and then composition'
        body=('用户认可E44的跨感官联系，提出进一步检验抽象关系、双向通感及类似回忆或梦境的无提示活动。牵动不准是否由激活、抑制、耗竭、易化或衰减不合适造成，作为假设保留，不先下结论。决定先配平输入与视觉曝光、校准过程读出，必要时比较既有参数；独立验证后再决定研究预设，不静默替换旧默认。语言对应、未见组合、联想因果作用分别给出明确通过/未通过，不能以消融导致普遍衰弱冒充逻辑归因。背景与死亡、可塑抑制连接另议。Docker仅在实际使用时检查。' if lang=='zh' else
              'The user requested abstract relations, reciprocal sensory association and uncued recall/dream-like activity after E44. Excess activation or unsuitable inhibition, depletion, facilitation and decay remain hypotheses. Match input/visual exposure and calibrate process observation first, then compare existing parameters if needed. Independently validate research profiles before changing defaults. Give explicit lexical, unseen-composition and causal-mediation verdicts; general impairment after ablation is not specific reasoning evidence. Background/death redesign and plastic inhibitory links are deferred. Check Docker only when used.')
        text=f'### {title}\n\n{body}\n\n[讨论与原话 / Discussion](../../plans/language-calibration-and-composition.md) · [E45登记 / Registration](../../../../lab/explorations/2026-10-05-language-calibration/design.{lang}.md)'
        for path in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
            append(f'docs/{lang}/history/{path}',text)
        append(f'docs/{lang}/history/milestones.md','2026-10-05 — E45校准、双向联想与未见组合获准 / Calibration, reciprocal association and unseen composition approved. [Plan](../plans/language-calibration-and-composition.md).')
        append(f'docs/{lang}/plans/index.md','- [语言校准与未见组合 / Calibration and composition](language-calibration-and-composition.md)：E45。')
        append(f'docs/{lang}/plans/language-development.md','### 2026-10-05：后续实施\n\n[E45独立校准与组合计划 / Calibration and composition](language-calibration-and-composition.md) 已获准；保留E44结论与原始证据，后续外设/参数选择先校准后验证。 / Approved without rewriting E44; select on calibration before held-out validation.')
        path=ROOT/f'docs/{lang}/plans/research-backlog.md'
        lines=path.read_text(encoding='utf-8').splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R17 /'):
                lines[i]=('| R17 / 当前推进E45 | 从零语言、双向感官联想与未见组合 | E44联系和局部因果作用保留；准确对应及表达待校准 | 已批准配平输入、校读出、有限调参、独立验证；逐项明确命题结论 | [E45](language-calibration-and-composition.md) |' if lang=='zh' else
                          '| R17 / E45 active | Scratch language, reciprocal sensory association and unseen composition | E44 effects/mediation retained; precision and expression open | Approved dose/instrument calibration, bounded parameters and held-out verdicts | [E45](language-calibration-and-composition.md) |')
            elif line.startswith('| R20 /'):
                lines[i]=('| R20 / P1，本任务校准获准 | 多机制参数的任务取舍 | E45先校外设，再比较有限单因素参数；未决定新默认 | 独立种子验证并报告准确、遗忘及无提示活动，保留原默认 | [E45登记](../../../lab/explorations/2026-10-05-language-calibration/design.zh.md) |' if lang=='zh' else
                          '| R20 / P1, task calibration approved | Parameter trade-offs | E45 peripherals first, bounded single-factor comparison; no new default selected | Validate held-out precision, forgetting and uncued activity | [E45](../../../lab/explorations/2026-10-05-language-calibration/design.en.md) |')
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md',text.replace('../../plans/','').replace('../../../../lab/','../../../lab/'))
    append('docs/zh/history/classical/shiji-05.md','### 校语议\n\n既见词能动象，研究者曰：当辨所记，亦当观象之反动词、寂处之自起。乃议先齐感官之量，次校器，后试核中旧参。不因一例合而称通语，亦不因未尽合而掩其已得；各立命题，各书成否，留旧法以相校。')
    append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：议校语与通感\n\n承E44，立E45。先齐教学入量，再验双向联想，必要则调旧参，别种复验。又议无显著教学时观其内动，欲察回忆之候。死生之法未改，背景仍存。未见组合及语义之成否，各据事前之约书之。')
    # Plans are reached through the existing history chapters and document menu;
    # no competing history copy or unnecessary new chapter is created here.
    catalog=json.loads((ROOT/'docs/history/catalog.json').read_text(encoding='utf-8'))
    for entry in catalog['chapters']:
        if entry['id'] in ('shiji-05','tongjian-04'):
            entry['period']=entry['period'].replace('2026-10-04','2026-10-05')
    (ROOT/'docs/history/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
