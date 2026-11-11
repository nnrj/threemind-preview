"""Close the current research summary; append history without rewriting reports."""
from history import ROOT, append


def main():
    for lang in ('zh', 'en'):
        zh = lang == 'zh'
        report = f'../../../lab/explorations/2026-10-05-language-calibration/report.{lang}.md'
        title = '2026-10-05：E45完成，分别判定联系、模式与表达' if zh else '2026-10-05: E45 completed; separate pathways, patterns and expression'
        body = (
            'E45完成2041个来源／分支，累计记录模拟、训练及转译67.91分钟。等剂量输入和六项单因素校准未超过原稀疏逐字＋默认参数，故未改Core或默认。正常／反转教学的视觉→名字感官非零影响各24/36，关闭学习0/36；六处跨感官边静默使影响减少至少99.9813%，匹配其他边仍保留98.995%～165.205%。这是教学形成双向联系的因果证据，不能再用正确名字0/36把它隐去。原物体准确取回10/72、二步名字→声音0/48；第二段后第一段联系本身也不可靠，组合缺口尚未单独定位。15条300秒连续过程没有登记条件下的晚期感官回放候选。'
            if zh else
            'E45 completed 2041 sources/branches and recorded 67.91 minutes of simulation, training and decoding. Equal-dose routes and six parameter alternatives did not beat sparse character input with defaults; Core/defaults were unchanged. Visual cues influenced name channels in 24/36 normal and 24/36 reversed cases, versus 0/36 learning-off. Six target-edge interventions removed at least 99.9813%; matched-other-edge silence retained 98.995%–165.205%. These learned reciprocal effects must not be concealed by correct-name retrieval of 0/36. Original object retrieval was 10/72 and two-step name-to-sound 0/48; the first link also lacked reliable retrieval after second teaching, so a composition-specific gap is not isolated. Fifteen 300-second histories contained no registered late sensory replay candidate.'
        )
        native = (
            '用户进一步提出，内部表征可以是感觉、过程、多个意向或抑制，不必复制外界视觉；交流只需共同对象的对应可用。遂事后登记、只重读既存轨迹：名字与“名字是”找回同一内部模式，正常12/36、反转9/36，关闭学习无可分辨模式；跨延迟／反转不稳。两种子同为3/24的旧计数实际来自不同提示，不能独自证明共同深层关系。本次补充不是改写原准确取词判据，也未穷尽抑制等非激活编码。下一步建议让表达器适应个体模式，再冻结外设验新经历；可靠交流、更多情境、抑制／传输过程及两段关系保持仍待研究。'
            if zh else
            'The user emphasized feelings, processes, multiple intentions and inhibition as possible native representations; communication need not reproduce an external visual template. A post-result registered rereading found name/name-plus-is pattern matches of 12/36 normal and 9/36 reversed, with no discriminable learning-off patterns; delay/reversal stability remained weak. Two earlier 3/24 totals involved different cues and do not alone prove a common hidden rule. This supplement does not replace exact-retrieval criteria or exhaust non-activation codes. Recommended next work adapts expression to individual patterns, freezes peripherals for new-experience attribution, retains both component relations and broadens contextual/inhibitory/transmission observations.'
        )
        text = f'### {title}\n\n{body}\n\n{native}\n\n[完整结果 / Results]({report}) · [讨论及原话 / Dialogue](language-calibration-and-composition.md)'
        path = ROOT / f'docs/{lang}/plans/research-backlog.md'
        lines = path.read_text(encoding='utf-8').splitlines()
        summary = (
            '**更新至2026-10-05：E45校准、双向联系、二步任务与连续观察已完成。教学形成双向跨感官影响，六处消融已定位；内部模式有部分复现。稳定取词、组合和晚期感官回放未通过或未检出。有限调参无增益，内核默认保留。下一步建议优先对接个体内部模式与表达，并分离第二段教学的保持／干扰问题；社会交流和长期具身发育未启动。**'
            if zh else
            '**Updated 2026-10-05: E45 calibration, reciprocal pathways, composition and continuous observation are complete. Teaching creates reciprocal influence localized at six sources; native patterns partly recur. Stable naming/composition did not pass and late sensory replay was not detected. No parameter candidate improved on defaults. Recommended next work connects individual patterns to expression and separates second-course retention/interference; social communication and long embodied development remain unstarted.**'
        )
        for i, line in enumerate(lines):
            if line.startswith(('**更新至2026-10-05：', '**Updated2026-10-05:', '**Updated 2026-10-05:')):
                lines[i] = summary
            elif line.startswith('| R17 /'):
                lines[i] = (f'| R17 / E45本批完成，继续研究 | 语言、通感与组合 | 双向影响及六处通路因果作用成立；稳定回答、二步组合未通过 | 优先个体模式表达；分离第二段保持与干扰，再验组合；建议非已启动 | [E45]({report}) |' if zh else
                            f'| R17 / E45 batch complete, continuing | Language, reciprocal senses and composition | Reciprocal influence and six localized causal effects; reliable answers/composition not passed | Recommend native-pattern expression and second-course retention/interference controls; not started | [E45]({report}) |')
            elif line.startswith('| R20 /'):
                lines[i] = (f'| R20 / 本任务有限校准完成 | 参数的任务取舍 | 六个单因素候选均未超过默认；原默认保留 | 不以阴性有限扫描判机制无用；更广多任务校准后议 | [校准结果]({report}) |' if zh else
                            f'| R20 / Bounded task calibration complete | Parameter trade-offs | Six single-factor candidates did not beat default; defaults retained | No general mechanism rejection from this grid; broader multitask calibration remains open | [Results]({report}) |')
            elif line.startswith('| T07 /'):
                lines[i] = ('| T07 / P2，持续完善 | 双向语言外设与过程转译工具 | E45增加配平输入、实际时间过程比较、物理振子听觉、分感官表达及个体模式检查；宽窄屏连续回放已验 | [工具](../reference/sensory-calibration-tools.md)。实时在线语言头／主聊天集成仍待完成，离线回放不冒充 |' if zh else
                            '| T07 / P2, continued | Bidirectional peripherals and process expression | E45 adds matched dose, actual-time comparison, physical oscillator sound, modality heads/native-pattern checks and responsive replay | [Tools](../reference/sensory-calibration-tools.md). Live language-head/main-chat integration remains open; offline replay is not that integration |')
        if not any(line.startswith('| C23 |') for line in lines):
            i = next(i for i, line in enumerate(lines) if line.startswith('| C22 |'))
            lines.insert(i+1, f'| C23 | {"E45校准、双向通感与内部模式" if zh else "E45 calibration, reciprocal pathways and native patterns"} | {"2041来源／分支；六处双向影响因果定位；部分模式复现；稳定取词和组合未通过；默认未变" if zh else "2041 sources/branches; six reciprocal effects localized; partial pattern recurrence; naming/composition not passed; defaults unchanged"} | [E45]({report}) |')
        # Replace the current cross-topic priority sentence, leaving dated entries below intact.
        for i, line in enumerate(lines):
            if line.startswith(('**The newest priority gap', '**当前最新的优先缺口', '**目前新增加的重点未结问题是')):
                lines[i] = ('**语言主线当前缺口是个体内部模式与可用表达的对接，以及追加教学后的关系保持。海洋摄食优势的整体机制归因等旧问题仍保留，见稳定条目；不混成正在执行的新批次。**' if zh else
                            '**The active language gap is usable expression of individual patterns and retention through additional teaching. Older whole-population feeding-attribution questions remain under their stable IDs; they are not new running batches.**')
        path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md', text)
        histtext = f'### {title}\n\n{body}\n\n{native}\n\n[报告 / Report](../../../../lab/explorations/2026-10-05-language-calibration/report.{lang}.md) · [原话及解释](../../plans/language-calibration-and-composition.md)'
        for file in ('chronicles/07-priority-experiments.md', 'themes/02-instruments.md', 'sources/source-register.md'):
            append(f'docs/{lang}/history/{file}', histtext)
        append(f'docs/{lang}/history/milestones.md', f'2026-10-05 — E45：{"双向联系被因果定位，内部模式与准确表达分立；默认保留" if zh else "reciprocal pathways localized; native patterns separated from exact expression; defaults retained"}. [Report](../../../lab/explorations/2026-10-05-language-calibration/report.{lang}.md).')
        append(f'docs/{lang}/plans/language-development.md', f'### {title}\n\n{body}\n\n{native}\n\n[Report]({report})')
        append(f'docs/{lang}/plans/language-calibration-and-composition.md', f'## {title}\n\n{body}\n\n{native}\n\n[Report]({report})')
    append('docs/zh/history/classical/shiji-05.md', '### 得意与达言\n\nE45既毕，凡二千四十一源与支，核法未改。见象能动名所居，习者有之，止学者无之；六处断其交络，动几尽灭，断旁络则多存。于是知通感有实，不可因言未中而谓心无所动。研究者又曰：意或为象，或为势，或为抑，众心异构，苟其所指同，亦可相通。乃以自身之迹相校，见同名异辞偶能复现，久隔及易所指则未固。言之可用、二义之相推、晚时之自忆，皆未验成，分书其得失，不移旧约。')
    append('docs/zh/history/classical/tongjian-04.md', '### 2026年10月5日：双向有迹，达言尚待\n\nE45毕。六法齐入量，六参各试，皆未胜旧，故留其常。象触名域，正常与反教各二十四中三十六，止学者无；六源断交络，影响减九成九以上，断旁络仍存。又以己迹为式，不拘外象，同名异辞有复现，而久隔及反教未稳。两段教学相继，后段象声可通，前段名象已弱，故不得专罪推理之法。观十五源，各三百秒，未见晚时感官自起之候。录原言，分联系、表征、达言三事，以俟后试。')


if __name__ == '__main__':
    main()
