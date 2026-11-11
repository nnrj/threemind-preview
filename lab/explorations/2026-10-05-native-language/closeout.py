"""Append E46 outcomes without rewriting older reports or decision criteria."""
from pathlib import Path
import shutil

from experiment import HERE, ROOT, WORK, OLD, read_json, new_json
from history import append


def main():
    for lang in ('zh','en'):
        zh=lang=='zh'
        outcome=('E46完成：723来源/副本、30个从零输出头。个体联想校准的视觉→名字7/12，共享2/12；只学直接感官的头能识别直接物体和裸名字，却跨感官0/36。随发育训练未胜相同资料冷训练。冻结后新经历门槛未过，未展开组合题。目标静默消除13个初始特异正确回答，匹配仅保留4个，故整体强归因条件未过。连续观察未见晚期感官再入，吐词也见于不学习对照。内核和默认未改。' if zh else
            'E46 completed723 sources/copies and30 scratch output heads. Individual association calibration gave7/12 visual-to-name matches versus2/12 shared; direct-sensation heads recognized direct objects/bare names but gave0/36 cross-sensory matches. Staged development did not beat cold training on the same history. Frozen-decoder new-experience gate failed; composition was not started. Target silence removed13 initial cue-specific correct responses; matched silence retained only4, so the overall strong attribution criterion failed. Continuous observation found no late sensory reentry; words also appeared in nonlearning controls. Core and defaults unchanged.')
        conclusion=(f'### 2026-10-05：E46完成，释读与表达分开\n\n{outcome}\n\n' if zh else
                    f'### 2026-10-05: E46 completed; interpretation and expression separated\n\n{outcome}\n\n')
        conclusion+=('[报告](../../../../lab/explorations/2026-10-05-native-language/report.zh.md) · [设计及补充](../../plans/native-expression.md) · [中枢适配器、原话与待议问题](../../reference/central-adapters.md)' if zh else
            '[Report](../../../../lab/explorations/2026-10-05-native-language/report.en.md) · [Design and supplements](../../plans/native-expression.md) · [Central adapters, original dialogue and open questions](../../reference/central-adapters.md)')
        for path in ('chronicles/07-priority-experiments.md','themes/02-instruments.md','sources/source-register.md'):
            # Chapters are four directories below root; source reports stay in place.
            append(f'docs/{lang}/history/{path}',conclusion)
        append(f'docs/{lang}/history/milestones.md',
            ('2026-10-05 — E46结项：个体活动释读有增益，冻结后的新对应未过；未改Core。[报告](../../../lab/explorations/2026-10-05-native-language/report.zh.md)。' if zh else
             '2026-10-05 — E46 closed: individual activity interpretation improved; frozen new-correspondence gate failed; Core unchanged. [Report](../../../lab/explorations/2026-10-05-native-language/report.en.md).'))
        append(f'docs/{lang}/plans/native-expression.md',
            ('## 2026-10-05 实施结项\n\n'+outcome+'\n\n[完整报告](../../../lab/explorations/2026-10-05-native-language/report.zh.md) · [直接感官校准补充](../../../lab/explorations/2026-10-05-native-language/calibration-source.zh.md) · [初始通路定位补充](../../../lab/explorations/2026-10-05-native-language/initial-mediation.zh.md)\n\n下一批建议先定位表达随时间失配，再研究有交流后果的输出选择；建议不自动授权新一批实验。' if zh else
             '## 2026-10-05 completion\n\n'+outcome+'\n\n[Full report](../../../lab/explorations/2026-10-05-native-language/report.en.md) · [Direct-sensation calibration supplement](../../../lab/explorations/2026-10-05-native-language/calibration-source.en.md) · [Initial mediation supplement](../../../lab/explorations/2026-10-05-native-language/initial-mediation.en.md)\n\nNext recommendation: locate expression drift, then study output choice in a communication environment. Recommendations do not automatically start another batch.'))
        append(f'docs/{lang}/reference/central-adapters.md',
            ('## E46结果对本定义的约束\n\n[实测报告](../../../lab/explorations/2026-10-05-native-language/report.zh.md)支持按实际联想活动校准，未证明必须共同发育，也未建立持续新知识表达。当前工具角色仍是观察释读。通用表达序列、主动使用与输出选择保持待议，不因新增名称而宣布实现。' if zh else
             '## Constraints from E46\n\n[Measured results](../../../lab/explorations/2026-10-05-native-language/report.en.md) support calibrating actual association patterns, not mandatory co-development or dependable new-knowledge expression. The current tool remains observational. A common expression sequence, purposeful use and output choice remain open; naming a role does not implement it.'))
        backlog=ROOT/f'docs/{lang}/plans/research-backlog.md'
        text=backlog.read_text(encoding='utf-8');lines=text.splitlines();inserted=False
        for i,line in enumerate(lines):
            if line.startswith('**更新至2026-10-05：') or line.startswith('**Updated through2026-10-05') or line.startswith('**Updated through 2026-10-05') or line.startswith('**Updated 2026-10-05:'):
                lines[i]='**'+outcome+'**'
            if line.startswith('| R17 /'):
                lines[i]=('| R17 / E46本轮完成，能力仍待改进 | 个体模式、共享与共同发育 | 初始个体表达有增益；冻结后新对应未过；直接感官与联想需分别校准 | 优先定位时间中的表示/读出失配，再检验持续校准与交流选择；不直接改Core | [E46报告](../../../lab/explorations/2026-10-05-native-language/report.zh.md) |' if zh else
                    '| R17 / E46 batch complete, capability open | Native patterns, sharing and co-development | Individual initial expression improved; frozen new knowledge failed; sensing/recall calibration differ | Locate temporal representation/readout drift before continuing calibration and communication choice; no automatic Core change | [E46](../../../lab/explorations/2026-10-05-native-language/report.en.md) |')
            if line.startswith('| T07 /'):
                lines[i]=('| T07 / P2，继续 | 双向外设与过程表达 | E46增加匿名过程投影、个体/共享/发育校准、样本注意力及冻结表达CLI，PC/手机原文回放已验 | [工具](../reference/native-expression-tools.md)；仍是实验性离线释读，日常聊天接入、主动表达与通用序列未实现 |' if zh else
                    '| T07 / P2, continued | Bidirectional peripherals and process expression | E46 adds anonymous projection, individual/shared/developmental calibration, prototype attention, frozen-expression CLI and responsive raw-text replay | [Tools](../reference/native-expression-tools.md); experimental offline interpretation, not live chat integration, voluntary expression or a universal sequence |')
        text='\n'.join(lines)+'\n'
        if '| C24 |' not in text:
            lines=text.splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('| C23 |'))+1
            lines.insert(idx,('| C24 | E46个体模式与语言释读 | 723例、30头；视觉→名字7/12对共享2/12；冻结新经历未过；目标/匹配屏蔽区分4个初始回答；未见可信晚期语言回放 | [E46](../../../lab/explorations/2026-10-05-native-language/report.zh.md) |' if zh else
                '| C24 | E46 native patterns and language interpretation | 723 cases/30 heads; visual naming7/12 vs shared2/12; frozen new experience failed; target/matched contrasts for4 initial prompts; no credible late verbal replay | [E46](../../../lab/explorations/2026-10-05-native-language/report.en.md) |'))
            text='\n'.join(lines)+'\n'
        backlog.write_text(text,encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md',
            ('### 2026-10-05：E46交付与后续优先项\n\n'+outcome if zh else '### 2026-10-05: E46 delivery and next priorities\n\n'+outcome)+
            ('\n\n当前优先待议：同一所指的内部表示随时间改变还是不可唤起；表达器持续校准如何避免把测试答案学进外设；内部活动释读与可主动使用的时序表达工具如何分开。原门槛保留，日常默认不变。[报告](../../../lab/explorations/2026-10-05-native-language/report.zh.md)。' if zh else
             '\n\nNext questions: temporal representation change versus failure to evoke; continued calibration without learning test answers in the peripheral; passive interpretation versus an expression tool the instance can use. Original gates and everyday defaults retained. [Report](../../../lab/explorations/2026-10-05-native-language/report.en.md).'))
    append('docs/zh/history/classical/shiji-05.md','### 释意既试\n\nE46既毕，三意识各习其译，视物得名七于十二，共用之译得二。直观之文虽能识物，移读联想则未合。乃知所习之迹有别。然更其所学，旧译不能随之；绝两感官之联，十三旧答皆失，绝他联亦失其九，不敢尽归一途。静观见译器犹吐词，而视听旧迹已息，未可据辞为思。遂分观者释意之器与意识行言之器，后者何时发、如何用，留待后验，未更核法。')
    append('docs/zh/history/classical/tongjian-04.md','### 2026年10月5日：E46毕\n\n试七百二十三例，育译头三十。各习内纹者，初视物而得名七于十二，共用者二；其后更教，定译未能从变。局部断联有别，然匹配亦多损，未尽明其由。无新教而吐词者，未皆由所言之物再起。乃记实而存原辞，分释意、表达二用，续议其序与发言之择；核及旧证皆如故。')
    frozen=WORK/'frozen-input';frozen.mkdir(exist_ok=True)
    for name in ('input-71.safetensors','input-71.json'):
        if not (frozen/name).exists():shutil.copy2(OLD/'models'/name,frozen/name)
    target=WORK/'frozen-tools/lab/tools/native_expression.py';target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(ROOT/'lab/tools/native_expression.py',target)
    print('E46 history/current backlog and source preservation updated')


if __name__=='__main__':main()
