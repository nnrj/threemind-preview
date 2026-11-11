"""Append decisions; preserve earlier evidence and stable backlog IDs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def append(path,text):
    p=ROOT/path;old=p.read_text(encoding='utf-8')
    if text.strip() not in old:p.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')

def main():
    for lang in ('zh','en'):
        title=('E48获准：原始状态、真实时序与表达归属' if lang=='zh' else 'E48 authorized: raw state, temporal experience and expression attribution')
        text=('用户要求保留原始响应，反对将无提示相减/单样本归一化作为表达；旧方法未改Core，但隐藏共同活动与幅度，须限定旧命名结论并复验。保留无对话缓存的表达器，区分读取Core过程与表达器独立记忆。先比较1/5/20/100ms递送及丰富状态，再研究共同参照、个体表达与关系迁移；空间基底不与这些因素混改。' if lang=='zh' else
              'The user rejected counterfactual subtraction and sample normalization as faithful expression. They did not modify Core but removed shared activity and magnitude; old naming evidence needs scoped interpretation and raw revalidation. Keep stateless decoding, distinguishing Core trajectory from decoder-owned dialogue memory. Compare1/5/20/100ms delivery and richer state before shared-reference/individual-expression/relational tests; do not mix spatial changes into this comparison.')
        link='[E48](../../plans/temporal-input-and-state-expression.md)'
        block=f'### 2026-10-05：{title}\n\n{text}\n\n{link}'
        for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
            append(f'docs/{lang}/history/{name}',block)
        append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — {title}：[E48](../plans/temporal-input-and-state-expression.md)。')
        append(f'docs/{lang}/plans/index.md',f'- [{title}](temporal-input-and-state-expression.md)')
        path=ROOT/f'docs/{lang}/plans/research-backlog.md';body=path.read_text(encoding='utf-8')
        marker='<!-- research-plan-current:start -->'
        note=('**E48执行中：本轮批准纠正表达读法、复验旧命名，比较句内毫秒间隔与更丰富原始状态。Core和旧证据保持；不把表达器的独立记忆当内核学习。**' if lang=='zh' else
              '**E48 active: raw-expression revalidation, millisecond input spacing and richer dynamical state are authorized. Core and old evidence stay intact; decoder-owned memory is not Core learning.**')
        if note not in body:body=body.replace(marker,marker+'\n\n'+note,1)
        lines=body.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R17 /'):
                lines[i]=('| R17 / E48执行中 | 原始表达、句内时间及关系迁移 | E47条件性命名保留，差值主读法已撤为分析工具 | 先原始复验、时间与状态，再共同发育和关系；不改Core | [E48](temporal-input-and-state-expression.md) |' if lang=='zh' else
                '| R17 / E48 active | Raw expression, within-sentence time and relation transfer | E47 conditional naming retained; differences are analysis only | Raw revalidation, timing/state, then development/relations; Core unchanged | [E48](temporal-input-and-state-expression.md) |')
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md',block.replace('../../plans/',''))
    append('docs/zh/history/classical/shiji-05.md','### 原迹与时序\n\n既有相减之读，能辨名而失其共动。用户谓释意当存原迹，不可因求可读而削其形。乃议E48：译器不自藏问答，取核中之态与历程；又使句中字次历时而至，以验其异。旧验存焉，原核不更。')
    append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：复验原始表达\n\n议语言之未通，用户疑所读未全、所入失时。遂定E48，先存原动，次试毫秒之隔，又察迹、势与连结。相减但为分析，不称意识原言；空间之议另列，毋杂其因。')

if __name__=='__main__':main()
