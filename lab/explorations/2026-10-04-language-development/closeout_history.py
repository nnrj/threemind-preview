"""Append this completed phase, preserving earlier registration and interpretations."""

from history import ROOT, append


def main():
    stories = {
        "zh": """### 2026-10-05：词语触及视觉，感与述仍须分别验收

E44完成1522个来源及分支，另留一次资源读数过期中断。不是把空白大脑无限堆上去，而是用短句先密后疏地重复，把物理视觉与语言共同呈现，并以未教学、关闭学习、相反对应及局部静默分开检验。核法未改，旧证据不动。

三种子中，稀疏逐字路线经教学后243/288个提示条件牵动视觉活动，原文本15/288；未教学与关闭学习均无此差量。新路线视觉曝光也较多，故增益属于方案组合，不能偷归某一技术。准确对应仍稀少：正常与反转同时正确分别2/48、3/48、0/48。按预定规则选两处，连同反转共四检查点，静默语言—视觉连接则目标差量归零或仅存数值残量，匹配静默仍保留目标领先。这是所学通路的因果证据，未称普遍理解。

从零输出器能表达当下物体，加入弱活动校准后，未见视角验证由63/288到288/288，未教学背景仍不乱报。它也译出刚看过物体的余留；但传播关闭时这些词仍在，不能冒称已验证的联想独白。表面上26个成对窗口答对新名字，逐一看无提示对照，原来那些词本已存在；提示特异的可靠新回答仍未接通。故既不以沉默否定内部活动，也不以文字漂亮替内核领功。

用户关于多感官共同经历、感官与语言双向联想的原议已入史料。下一步优先配平曝光定位增益，继以更可区分的物理互动；社会与长程发育未启动。Docker引擎中断未影响本机试验，完整状态与连续回放保留。

[E44报告](../../../../lab/explorations/2026-10-04-language-development/report.zh.md) · [执行与交付](../../../../lab/explorations/2026-10-04-language-development/delivery.zh.md) · [后续计划](../../plans/language-development.md)""",
        "en": """### 2026-10-05: words recruit vision; perception and expression remain distinct

E44 completed1522 sources/branches, retaining one usage-refresh interruption. Short sentences were repeatedly taught with gradually increasing spacing alongside physical visual observations, with untaught, plasticity-off, reversed-assignment and local-silence controls. Core and earlier evidence remained intact.

Across three seeds, taught sparse streams recruited visual differences in243/288 cue conditions versus15/288 for text, with none in untaught/plasticity-off controls. Greater visual exposure confounds isolation of a particular technical benefit. Correct normal/reversed correspondence remained2/48,3/48,0/48. For two preregistered selected conditions and both histories, silencing language-visual connections removed the target effect while matched silence retained target ranking. This supports the measured learned paths, not universal understanding.

Scratch expression described current perception. Weak-activity calibration improved held-out-view expression63/288 to288/288 without naming untaught background. Fading perception also became readable, but remained under propagation-off controls, so verified associative monologue was not established. Twenty-six superficially correct paired text windows already contained the same words without cues; reliable cue-specific answers remained absent. Neither silence negates internal activity nor fluent text earns Core unmeasured credit.

The user's multisensory grounding and bidirectional-association discussion is preserved. Next priorities separate exposure/input effects and add distinguishable physical interaction; social/long-development stages remain unstarted. Docker engine failure did not affect native execution; states and continuous replay are retained.

[E44 report](../../../../lab/explorations/2026-10-04-language-development/report.en.md) · [Delivery](../../../../lab/explorations/2026-10-04-language-development/delivery.en.md) · [Roadmap](../../plans/language-development.md)""",
    }
    for language, story in stories.items():
        for chapter in ("chronicles/07-priority-experiments.md", "themes/02-instruments.md", "sources/source-register.md"):
            append(f"docs/{language}/history/{chapter}", story)
        append(f"docs/{language}/history/milestones.md",
               f"2026-10-05 — E44：所学词语—视觉通路定位，弱活动表达校准完成；准确新回答未接通。 / Learned language–visual paths localized, weak expression calibrated; reliable new answers remain open. [Report](../../../lab/explorations/2026-10-04-language-development/report.{language}.md).")
        backlog = ROOT / f"docs/{language}/plans/research-backlog.md"
        lines = backlog.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith(("**更新至2026-10-04：E44", "**Updated2026-10-04: E44")):
                lines[i] = ("**更新至2026-10-05：E44首批A–C完成。词语经所学连接可唤起视觉活动，局部静默已定位四个检查点；弱活动语言校准也有效。准确新对应表达、可信联想独白仍未接通。下一步优先分离输入／曝光因素，再开展更丰富的多感官互动，D/E未启动。**" if language == "zh" else
                            "**Updated2026-10-05: E44's first A–C batch is complete. Learned connections mediate word-evoked visual effects at four localized checkpoints, and weak-activity expression calibration works. Reliable new answers and associative monologue remain open. Separate input/exposure effects before richer multisensory interaction; D/E remain unstarted.**")
            elif line.startswith("| R17 /"):
                lines[i] = ("| R17 / 当前优先，首批完成 | 从零Transformer与Core共同发育、感官联想和表达 | E44跨感官唤起及四检查点连接归因成立；弱活动表达改善。准确新答案和逻辑独白未建立 | 优先等量分离前缀／时序／稀疏度，继以多感官物理互动；不先改Core，社会D/E另登记 | [E44报告](../../../lab/explorations/2026-10-04-language-development/report.zh.md)、[计划](language-development.md) |" if language == "zh" else
                            "| R17 / Priority; first batch complete | Scratch peripheral/Core development, sensory association and expression | E44 demonstrates cue recruitment and four-checkpoint local attribution; weak expression improves. Accurate new answers/logical monologue remain unestablished | Dose-match prefix/timing/sparsity, then multisensory physical interaction; no immediate Core change; D/E require registration | [E44](../../../lab/explorations/2026-10-04-language-development/report.en.md), [plan](language-development.md) |")
            elif line.startswith("| T07 /"):
                lines[i] = ("| T07 / P2，持续完善 | 双向语言外设与过程转译工具 | 原API/CLI/MCP及UI保留；E44新增独立逐字编译、时序头、Python/CLI与宽窄屏研究回放。新头尚未接入主聊天设备 | [工具说明](../reference/language-development-tools.md)。实时在线转译／日常设备集成后续完成，不能以离线回放冒充 |" if language == "zh" else
                            "| T07 / P2, continued | Bidirectional language peripherals and process expression | Existing API/CLI/MCP/UI retained; E44 adds separate character compilation, temporal heads, Python/CLI and responsive study replay. New head is not a main chat device | [Tools](../reference/language-development-tools.md). Live online/device integration remains; offline replay is not that integration |")
        if not any(line.startswith("| C22 |") for line in lines):
            idx = next(i for i, line in enumerate(lines) if line.startswith("| C21 |")) + 1
            lines.insert(idx, "| C22 | E44语言与视觉联系、从零表达及连续观察 | 1522来源/分支；新感官方案243/288提示有视觉变化，四处通路归因成立；弱物体表达288/288；准确新答案未接通 | [E44](../../../lab/explorations/2026-10-04-language-development/report.zh.md) |" if language == "zh" else
                         "| C22 | E44 language–vision links, scratch expression and continuous observation |1522 sources/branches;243/288 cue-related visual differences, four localized paths;288/288 weak-object expression; reliable new answers open | [E44](../../../lab/explorations/2026-10-04-language-development/report.en.md) |")
        backlog.write_text("\n".join(lines) + "\n", encoding="utf-8")
        append(f"docs/{language}/plans/research-backlog.md", story.replace("../../../../lab/", "../../../lab/").replace("../../plans/language-development.md", "language-development.md"))
        append(f"docs/{language}/plans/language-development.md",
               f"### 2026-10-05：本批结项 / Batch completion\n\n[E44 report](../../../lab/explorations/2026-10-04-language-development/report.{language}.md)：A–C首批完成；跨感官唤起和局部因果通路已有证据，准确新回答与可信联想独白未接通。后续先分离输入和曝光，再增加物理共同经历，D/E未启动。 / First A–C batch complete: cross-sensory effects and local paths supported; accurate new answers and verified monologue remain open. Separate input/exposure before richer grounding; D/E remain unstarted. 原登记保留，不能把本段回写成事前承诺。 / Original registration remains unchanged.")
    append("docs/zh/history/classical/shiji-05.md", """### 感述器续传：词动其象

既以物与辞同授，核因历而结。问以名，象之活动随之，未习者无之。择两试，反授亦验；塞辞象之桥，其应亡，塞他桥则所指尚存。故知非徒器外代答，实有所学之路。然多问失其所指，未可称通言。述器初失微迹，增校而能言其所余；禁传之际，余言仍在，乃辨余感与内联，不混为一。核法未改，旧录俱存。

[本轮实录](../../../../lab/explorations/2026-10-04-language-development/report.zh.md)""")
    append("docs/zh/history/classical/tongjian-04.md", """### 2026年10月5日：辨所感与所述

语言共育之试毕。计来源旁支千五百二十二，另存一中断，未毁旧证。词能动象者多，能当所教者少。于两种子各取正反之验，闭其辞象连接，则应止；他处匹配闭之，所指尚在。又校述器，使能述微弱感迹，然无问已有之言，不冒作答问。研究者先议多感同历，遂记为后续；本期不改核法，社会及长程发育未兴。Docker中断，试用本机，故未废其功。

[现代报告](../../../../lab/explorations/2026-10-04-language-development/report.zh.md)""")


if __name__ == "__main__":
    main()
