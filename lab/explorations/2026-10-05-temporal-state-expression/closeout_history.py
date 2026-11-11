"""Append E48 measured findings and the dated scoring correction."""
from history import append,ROOT


def main():
    for language in ('zh','en'):
        zh=language=='zh'
        narrative=('E48完成1242项来源/分支/探针与19个表达器候选。0/1/5/20/100ms未改善指定命名；1ms新对应对照与0ms同分。原始全状态/过程保留，不相减或逐样本归一化。表达器1200步多数仅拟合4～7/18，延长6000步到14/18仍未过17/18门槛。连续扫视在新物体上全节点16/16，但关学习仍16/16，排除直接感官8/16；有顺序痕迹，尚非教学带来的关系迁移。'
            '本期重要更正：阶段A的9/12→12/12是提示特异评分变化，实际命名均12/12；原输出未被改动。主表改为同时呈现实际正确、旧评分和无提示原文，不以空白监督否定自主活动。额外无空白监督对照保留当前6/8，但新对应仍未通过。未改Core/default，未推翻海洋既定干预结果。'
            if zh else
            'E48 completes1242 sources/branches/probes and19 candidate decoders.0/1/5/20/100ms do not improve the specified naming task;1ms new-mapping controls match0ms. Raw state/process is preserved without subtraction or sample normalization. Most1200-step decoders fit only4–7/18;6000 steps reach14/18 but not the17/18 gate. Event order yields16/16 on new objects, also16/16 without learning; direct-sensor exclusion yields8/16. Order traces exist, but learned relational transfer is not shown. '
            'A dated correction separates actual accuracy from cue specificity: the earlier9/12→12/12 had actual naming12/12 in both cases. Original outputs were unchanged. Main tables now present actual accuracy, old scoring and no-cue text separately; blank supervision cannot disprove autonomous activity. An unlabelled-no-cue control retains current6/8 but fails new mappings. Core/defaults and the established ocean interventions remain intact.')
        report=f'../../../lab/explorations/2026-10-05-temporal-state-expression/report.{language}.md'
        source=f'../../../../lab/explorations/2026-10-05-temporal-state-expression/report.{language}.md'
        block=('### 2026-10-05：E48原始表达复验与评分更正' if zh else '### 2026-10-05: E48 raw-expression revalidation and score correction')+'\n\n'+narrative
        for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
            # These files are one level below history/.
            append(f'docs/{language}/history/{name}',block+f'\n\n[报告 / Report]({source})')
        append(f'docs/{language}/history/milestones.md',block+f'\n\n[报告 / Report](../../../lab/explorations/2026-10-05-temporal-state-expression/report.{language}.md)')
        path=ROOT/f'docs/{language}/plans/research-backlog.md';text=path.read_text(encoding='utf-8');lines=text.splitlines();out=[]
        for line in lines:
            if line.startswith('**E48'):
                line=('**E48本轮完成：原始表达复验、五种句内间隔、完整状态和连续事件对照已做。主要新定位是表达器欠拟合；9/12→12/12的解释已更正为评分差异。Core未改。下一步优先可靠校准、跨时间/经历表达，再判断语言与关系迁移。**' if zh else
                      '**E48 round complete: raw expression, five within-sentence intervals, richer state and continuous-event controls. Decoder underfitting is identified;9/12→12/12 is corrected as a scoring difference. Core unchanged. Prioritize reliable calibration and cross-time/experience expression before judging language/relational transfer.**')
            if line.startswith('| R17 /'):
                line=(f'| R17 / 本轮完成、继续 | 原始表达、句内时间及关系迁移 | E48时序无增益，表达器欠拟合；事件顺序痕迹无需学习也存在 | 先跨时间/经历翻译校准；一般关系、共享/个体表达及独白未结 | [E48]({report}) |' if zh else
                    f'| R17 / Round complete, continue | Raw expression, input time and relation transfer | E48 timing gives no naming gain; decoders underfit; event order is readable without learning | Cross-time/experience calibration first; general relations, shared/personal expression and monologue remain open | [E48]({report}) |')
            if line.startswith('| T07 /'):
                line=(f'| T07 / P2，继续 | 双向外设与过程表达 | E48原始/图状态CLI、101点过程、逐题查看及评分拆分已验；完整观察不改变旧探针轨迹 | [工具](../reference/raw-state-expression.md)；生产聊天及可靠自主表达仍未完成 |' if zh else
                    '| T07 / P2, continue | Bidirectional adapters and process expression | E48 raw/graph-state CLI,101-point processes, item viewer and separate scoring verified; full observation preserves an old probe | [Tools](../reference/raw-state-expression.md); production chat and reliable autonomous expression remain incomplete |')
            out.append(line)
            if line.startswith('| C25 |') and not any(x.startswith('| C26 |') for x in lines):
                out.append((f'| C26 | E48原始状态、时序及表达复验 | 1242项、19头；五间隔及1ms新对应无增益；表达器欠拟合；事件顺序16/16但无学习也相同；评分更正已追加 | [E48]({report}) |' if zh else
                    f'| C26 | E48 raw-state/time/expression revalidation | 1242 cases,19 heads; five intervals and1ms new mappings show no gain; underfitting; event order16/16 also without learning; scoring correction appended | [E48]({report}) |'))
        path.write_text('\n'.join(out)+'\n',encoding='utf-8')
        append(f'docs/{language}/plans/research-backlog.md',block+f'\n\n[报告 / Report]({report})')
        append(f'docs/{language}/plans/temporal-input-and-state-expression.md',block+f'\n\n[报告 / Report]({report})')
        append(f'docs/{language}/reference/raw-state-expression.md',
            ('2026-10-05交付补充：实际答对与提示特异评分并列；无提示的空白不是真值，不能据此过滤表达或断言无自主活动。[E48更正](../../../lab/explorations/2026-10-05-temporal-state-expression/scoring-correction.zh.md)' if zh else
             '2026-10-05 delivery addition: actual correctness and cue specificity are separate. No-cue blank is not semantic ground truth and must not filter expression or disprove autonomous activity. [Correction](../../../lab/explorations/2026-10-05-temporal-state-expression/scoring-correction.en.md)'))
    append('docs/zh/history/classical/shiji-05.md','### 译未明与分之异\n\nE48既验，句中略隔其时，名之辨未进；尽取迹势连结，译者犹未习其职。延其学，十八中十四，尚未及所约。又观相机往复，新物亦辨其序，禁学者亦然，故知有时迹而未可尽称学得其理。初记名中九，复核原答实十二，旧以无问同言去三：是分之异，非答之失。乃并书原答与旧分，无问之言不遽削焉。核不更，先审译器，而后议所缺。')
    append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：原始表达实验结项\n\nE48凡来源分支探测千二百四十二，译器十九。五种句内间隔，无独善者；原态可辨，译未尽成。连续扫视虽有序迹，禁学亦可辨，未以此称关系已学。复正九中十二之说，实答皆十二，异在无问之判。于是存旧证，列新解，戒以仪器未明而先罪内核。')


if __name__=='__main__':main()
