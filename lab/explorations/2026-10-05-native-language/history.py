"""Dated decisions and user-facing adapter terminology, preserving older records."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    file=ROOT/path
    old=file.read_text(encoding='utf-8')
    if text.strip() not in old:
        file.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


def main():
    for lang in ('zh','en'):
        discussion=('E45之后，用户提出表达器应学习意识自身的内部模式，并比较共享、个体专用与共同发育。批准E46：先重读六路输入旧轨迹，再以新Core实例比较两类读出、四种训练方式，冻结外设后改变教学以定位新知识的来源。普通教学、原内核和背景保留。进行中补充“中枢适配器”：是面向任务和使用者的重要性分类，不是Core的新层或特殊权限；语言、视觉、听觉和运动按需选配。' if lang=='zh' else
            'After E45, the user authorized adapters that learn native individual patterns, comparing shared, individual and developmental expression. E46 re-reads six old input routes, then compares two readers and four training regimes on new Core instances. Freeze adapters before changing teaching to attribute new knowledge. Ordinary teaching, Core and background remain intact. During execution, the user proposed central adapters as a task/user-facing category, not an extra Core layer or privileged access; language, vision, hearing and motor roles are optional.')
        links='[E46](../../plans/native-expression.md) · [中枢适配器 / Central adapters](../../reference/central-adapters.md)'
        block=f'### 2026-10-05：个体模式表达与中枢适配器 / Native expression and central adapters\n\n{discussion}\n\n{links}'
        for chapter in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
            append(f'docs/{lang}/history/{chapter}',block)
        append(f'docs/{lang}/history/milestones.md',
            '2026-10-05 — E46获准 / E46 authorized: [个体模式表达 / Native expression](../plans/native-expression.md); [中枢适配器 / Central adapters](../reference/central-adapters.md).')
        append(f'docs/{lang}/plans/index.md','- [个体内部模式与语言表达 / Native patterns and expression](native-expression.md)：E46。')
        for page in ('architecture-boundaries.md','v2-adapters-and-capabilities.md','language-adapters.md'):
            if not (ROOT/f'docs/{lang}/{page}').exists():
                continue
            append(f'docs/{lang}/{page}','### 2026-10-05：中枢适配器 / Central adapters\n\n'
                '[面向任务的功能分类与边界 / Task-facing roles and boundaries](reference/central-adapters.md)。协议和Core权限不因名称改变；不是预设脑区。 / The name changes neither protocol nor Core privileges and creates no predefined brain region.')
        file=ROOT/f'docs/{lang}/plans/research-backlog.md'
        lines=file.read_text(encoding='utf-8').splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R17 /'):
                lines[i]=('| R17 / E46正在执行 | 个体内部模式表达、共享与共同发育 | E45联系/因果证据保留，可靠表达仍待建立 | 新实例比较共享/个体/分阶段训练；冻结解码器验新经历；不改Core | [E46](native-expression.md) |' if lang=='zh' else
                    '| R17 / E46 active | Native expression, sharing and co-development | E45 effects/mediation retained; reliable expression open | Compare shared/individual/developmental output and frozen-decoder new experience; Core unchanged | [E46](native-expression.md) |')
        file.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md',block.replace('../../plans/','').replace('../../reference/','../reference/'))
    append('docs/zh/history/classical/shiji-05.md','### 释意之器\n\n有内动而未能言，研究者谓当令译器习其各自之文，毋强其形似外物。乃立E46，比共用、各习与随长而习；译器既定，复更所教，以验所记在何处。又名语言、视、听、运动之器为中枢适配器，谓其要于用者，非增核中之权也。')
    append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：试因人释意\n\n承E45，议令表达之器识各意识内纹。立E46，先复读旧迹，次育新例，后定译器而更其学。又议中枢适配器之名，随事设之，与诸外设同法，未改核中运行。')


if __name__=='__main__':main()
