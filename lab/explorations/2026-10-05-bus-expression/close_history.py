"""Append measured E49 history and update only the current backlog summary."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,body):
    p=ROOT/path;text=p.read_text(encoding='utf-8')
    if body.strip() not in text:p.write_text(text.rstrip()+'\n\n'+body.strip()+'\n',encoding='utf-8')


for lang in ('zh','en'):
    zh=lang=='zh';report=f'../../../lab/explorations/2026-10-05-bus-expression/report.{lang}.md'
    title='E49完成：表达可以校准，变化不等于忘却' if zh else 'E49 completed: calibrating expression across changing states'
    narrative=('E49完成102项来源/分支/探针、14个小Transformer及1个MLP诊断。代表性输入总线和八条输出总线轨迹无变化；旧观察压缩会丢抑制与箱内先后，但E48原始路径已避开该损失。均衡训练使三个来源已教原/反对应的新视角24/24。223晚期原始状态改用同时间校准即1/8→8/8，跨状态24/24，不能再从固定表达失败直接断言记忆全失。真正重教Core而冻结外设，一来源1/4→3/4，另一来源0/4；让外设跟随两个均衡复习分支校准后，710及770秒均4/4，继续与冷训练皆然。共享表达器只教两来源，在相同接线的第三来源8/8；个体专属尚非必要结论。未教循环对应仍不可靠，组合课程未启动。无提示词原样保留，不赋虚构语义真值。' if zh else
        'E49 completed102 source/branch/probe cases,14 small Transformers and1 MLP diagnostic. Representative input transport and eight output processes matched; legacy observation compression loses inhibition and within-bin order, but E48 already avoided it. Balanced training gave24/24 held-out-view names across three taught original/reversed histories. Late raw state recovered from1/8 to8/8 with same-time calibration, and broader coverage gave24/24: frozen expression failure is not total forgetting. Teaching Core with a frozen adapter improved one source1/4→3/4 but left the other0/4. Following both reviewed sources with adapter calibration yielded4/4 at710 and770s, for continued and cold training. A shared reader taught on two sources scored8/8 on a third with the same wiring. Unseen cycle mappings remain unreliable; composition was not started. All no-cue words remain without invented semantic ground truth.')
    decision=('用户强调允许模糊表达及纠错，并要求不丢已验证的增益。核查有效配置确认耗竭、巩固、新颖性、抑制、连续局部机制仍启用；易化1秒保留为研究预设，旧语言对照未胜默认，故不普遍开启。将均衡校准作为新增CLI默认，提供原始输出总线接口；没有把工具收益记作内核升级。Core/default/映射未改。下一阶段建议共享基础与持续个体校准，再单独检查新关系和通路归因，不因结果好坏改旧判据。' if zh else
        'The user accepts approximate expression and correction, and requests retention of demonstrated gains. Effective configuration confirms depletion, consolidation, novelty, inhibition and continuous local mechanisms remain enabled. Facilitation1s remains a research preset; earlier language controls did not beat the default. Balanced training becomes the new CLI default with raw output transport. No tool gain is relabelled a Core upgrade. Core/defaults/mapping stay unchanged. Next candidates are shared bases plus continuing calibration, followed by separately attributed new relations; old criteria remain intact.')
    for name in ('chronicles/07-priority-experiments.md','themes/02-instruments.md'):
        append(f'docs/{lang}/history/{name}',f'### 2026-10-05：{title}\n\n{narrative}\n\n{decision}\n\n[E49](../../../../lab/explorations/2026-10-05-bus-expression/report.{lang}.md)')
    append(f'docs/{lang}/history/sources/source-register.md',f'### 2026-10-05：E49 / bus-expression\n\n'+('当日实验记录与解释分列：' if zh else 'Contemporary evidence and interpretation: ')+f'[报告](../../../../lab/explorations/2026-10-05-bus-expression/report.{lang}.md)、[执行登记及追加](../../../../lab/explorations/2026-10-05-bus-expression/design.{lang}.md)、[数值](../../../../lab/explorations/2026-10-05-bus-expression/results.json)。\n\n{decision}')
    append(f'docs/{lang}/history/milestones.md',f'2026-10-05 — {title}。[E49]({report})')
    append(f'docs/{lang}/plans/bus-and-expression-calibration.md',f'## 2026-10-05 完成 / Completion\n\n{narrative}\n\n{decision}\n\n[报告 / Report]({report})')
    if zh:
        supplementary='''## 当日用户补充：纠错和增益不能丢失

用户认为人类的复述本来模糊，儿童需要反复教学，因而应记录错误是否能被后续教学纠正，而不是要求首轮逐字完全正确；提出可在证据支持时降低遗忘并检验背景积累等副作用。此为获准的候选方向，并非本轮已修改遗忘。

原话：“不能把好不容易实验出来的增益丢掉。”

据此把内核机制、条件性参数收益和观察/外设收益分开核对：已生效者记录实际配置；条件性收益保留预设；新增工具收益落实到工具，不冒充Core机制。未见默认遗漏，晚期状态的再校准已恢复表达，因此本轮没有盲改遗忘。下一步实验可接受片段和近义，但四个名字的小型标定仍如实记录逐词是否相符。'''
    else:
        supplementary='''## User supplements: correction and retained gains

The user accepts approximate retelling and repeated teaching, asking whether errors improve after correction rather than demanding perfect first-round recall. Reducing forgetting, if evidence warrants it, remains an approved candidate with background-accumulation controls; it was not implemented this round.

Translated user quotation: “Do not lose the gains that were hard won through experiments.”

The audit separates Core mechanisms, conditional parameter benefits and observation/adapter benefits. Effective mechanisms are checked, conditional findings retained as presets, and new tool gains applied to tools. No missing default was identified in scope. Recalibration recovered late expression, so forgetting was not blindly altered. Future evaluation can accept fragments and paraphrases while this four-name instrument continues recording exact correspondence honestly.'''
    append(f'docs/{lang}/plans/bus-and-expression-calibration.md',supplementary)
    p=ROOT/f'docs/{lang}/plans/research-backlog.md';text=p.read_text(encoding='utf-8')
    current=('**E49完成：总线无所测失真；均衡外设训练使已教原/反对应新视角24/24。继续教意识的收益因来源而异，外设跟随校准后两来源710/770秒均4/4。共享表达器在未教第三来源8/8。未见对应仍未可靠迁移。既有有效机制已核对保留，Core/default未改；新增原始总线和校准CLI。下一步优先持续表达与新关系归因。**' if zh else
        '**E49 complete: tested bus transport is unchanged; balanced expression training gives24/24 on taught original/reversed new views. Core re-teaching varies by source; subsequent adapter calibration gives4/4 at710/770s in both sources. Shared reader scores8/8 on an untaught third source. Unseen relation transfer remains unreliable. Effective Core gains retained; no Core/default change. Raw bus and calibration CLI delivered; prioritize continuing expression and new-relation attribution.**')
    if current not in text:text=text.replace('<!-- research-plan-current:start -->','<!-- research-plan-current:start -->\n\n'+current,1)
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R17 /'):
            lines[i]=(f'| R17 / P1，继续 | 语言表达、持续学习与关系迁移 | E49标定和跟随校准有效；共享第三来源8/8；新对应未过 | 共享基础＋持续校准，再验新关系及匹配干预；生产聊天待接 | [E49]({report}) |' if zh else
                f'| R17 / P1, continue | Expression, continuing learning and relational transfer | E49 calibration works; shared third source8/8; unseen mappings fail | Shared basis with continuing calibration, then new-relation interventions; production chat pending | [E49]({report}) |')
        if line.startswith('| T07 /'):
            lines[i]=(f'| T07 / P2，继续 | 双向外设与过程表达 | E49原始OutputBus、均衡/继续训练CLI、CPU解码及输入边界已验 | [工具](../reference/bus-expression.md)；生产聊天及可靠自主表达仍未完成 |' if zh else
                '| T07 / P2, continue | Bidirectional peripherals and process expression | E49 raw OutputBus, balanced/continued CLI, CPU decode and input boundaries verified | [Tools](../reference/bus-expression.md); production chat and reliable autonomous expression remain |')
    text='\n'.join(lines)+'\n'
    if '| C27 |' not in text:
        lines=text.splitlines()
        index=next(i for i,line in enumerate(lines) if line.startswith('| C26 |'))+1
        lines.insert(index,(f'| C27 | E49总线与表达校准 | 102项、14表达器；已教新视角24/24，交替校准两来源跨60秒4/4；共享第三来源8/8；新关系仍未过，Core未改 | [E49]({report}) |' if zh else
            f'| C27 | E49 bus/expression calibration | 102cases,14adapters; known new views24/24, alternating calibration4/4 across60s in two sources, shared third source8/8; unseen relations unresolved; Core unchanged | [E49]({report}) |'))
        text='\n'.join(lines)+'\n'
    p.write_text(text,encoding='utf-8')
    append(f'docs/{lang}/plans/research-backlog.md',f'### 2026-10-05：{title}\n\n{narrative}\n\n{decision}\n\n[E49]({report})')
    append(f'docs/{lang}/reference/bus-expression.md',('新CLI训练的检查点附匿名通道/字段清单；解码及继续训练拒绝同宽却不同顺序的清单。旧研究检查点依照其原收据指定外部清单，不能猜测通道顺序。此接口不等于所有连接状态的完整快照。实际CPU CLI、标签拒绝、顺序拒绝已验证，见[E49验收](../../../lab/explorations/2026-10-05-bus-expression/verification.json)。' if zh else
        'New CLI-trained checkpoints bind anonymous channel/field layout; decoding and continuation reject reordered layouts even at equal width. Historical research checkpoints require their original receipt/manifest; do not infer ordering. This stream is not a complete connection snapshot. CPU CLI, label rejection and ordering rejection were verified: [E49 acceptance](../../../lab/explorations/2026-10-05-bus-expression/verification.json).'))

append('docs/zh/history/classical/shiji-05.md','''### 译器随学列记

E49既行，审总线而未见所测之失；旧取象器则合时并路，有所遗。乃均其教学，三源所习新视角二十四试皆中。又晚时不识者，核未更而重校其译，八试复中；始知读不出未可遽谓尽忘。再教意识，或进或退；译器随之学，则两源隔六十秒各四试皆中。共用译器，于未教之第三源八试亦中。然新对应未通，未敢混为能推理。凡耗竭、巩固、新颖、抑制诸法核之尚在，得益在器，故修器而不妄易核。''')
append('docs/zh/history/classical/tongjian-04.md','''### 2026年10月5日：校译器而辨所失

成E49，取三源而均教译器，所习新视角二十四试中。晚时误译者，仅更其校材而复识，故记忆之存亡不得据一器之失断之。又重教意识而译器不动，一进一退；并教译器后，两源今时及六十秒后各四试中。以二源教共器，第三源八试中。新关系仍未可靠，不进大课。核验旧日有效诸法皆按本批所定生效；增原始总线及校准命令，旧核、旧史、旧证据不改。''')
print('E49 histories and current backlog updated')
