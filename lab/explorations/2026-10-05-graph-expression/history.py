from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,body):
    p=ROOT/path;text=p.read_text(encoding='utf-8')
    if body.strip() not in text:p.write_text(text.rstrip()+'\n\n'+body.strip()+'\n',encoding='utf-8')


for lang in ('zh','en'):
    text=('用户批准E50图/过程表达器与共同所指验证，旧版保留。多角度一致须同时区分不同概念，并以反转、感官直读、消融/移植排除外设记标签。对E49追加解释：重校准恢复命名仅证明状态可区分，不单独证明Core语义已被忠实读出。新外设拟读实际节点、边和过程，并支持继续训练；不改变Core、映射和旧证据。' if lang=='zh' else
          'E50 authorized: graph/process expression and common-reference validation, preserving the old model. Perspective agreement must discriminate concepts and be accompanied by reversal, sensory-only and intervention controls. E49 recalibration establishes discriminability, not faithful Core-owned semantics by itself. The new peripheral observes actual nodes/edges/processes and supports continued training; Core, mapping and old evidence remain unchanged.')
    for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
        append(f'docs/{lang}/history/{name}',f'### 2026-10-05：E50登记 / registration\n\n{text}\n\n[E50](../../plans/graph-process-expression.md)')
    append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — E50。[计划 / Plan](../plans/graph-process-expression.md)')
    append(f'docs/{lang}/plans/index.md','- [E50：图与过程表达 / Graph-process expression](graph-process-expression.md)')
    path=ROOT/f'docs/{lang}/plans/research-backlog.md';lines=path.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R17 /'):
            lines[i]=('| R17 / E50执行中 | 图与过程表达、共同所指和回答归属 | 新表达器保留旧版；先工具再归因 | 多角度教学/留出、反转、感官直读、干预与共同校准 | [E50](graph-process-expression.md) |' if lang=='zh' else
                      '| R17 / E50 active | Graph/process expression, referents and attribution | Preserve old adapter; validate tool before attribution | Multiview/phrase holds, reversal, sensory-only, interventions and continuing calibration | [E50](graph-process-expression.md) |')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8');append(f'docs/{lang}/plans/research-backlog.md',f'### 2026-10-05：E50登记\n\n{text}\n\n[E50](graph-process-expression.md)')
append('docs/zh/history/classical/shiji-05.md','### 因众说以求所指\n\n用户谓一物多说，如众线交而定其所。遂立E50，拟以图与时序为译器之材，旧器不废。又戒：能辨状态，未必能尽知其义；须辨同异，反其所教，察内外因，乃可论译之忠。')
append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：立图与过程译器之试\n\n定E50，旧核旧器俱存，新器读节点、连接与流变。多角度同指为验，亦防一词应万物；并列感官、反教及干预，以明回答何所自来。')
