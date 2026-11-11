"""Register this approved phase without replacing older decisions or results."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def append(path, text):
    file = ROOT / path
    current = file.read_text(encoding="utf-8")
    if text.strip() not in current:
        file.write_text(current.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


def main():
    entries = {
        "zh": """### 2026-10-04：从零语言共同发育独立立项

E43留下持久结构而未可靠唤起或转译新对应。研究者问：已有经历、记忆、顺序与内部活动的证据，是否可以通过共同训练的小Transformer成为可持续学习的语言系统；是否需要社会交流或重演地球演化。助手区分输入、唤起、关系组合和表达，建议先做具身共同经历与从零外设，社会交流随后，长期演化后置。用户批准，并特别要求连续观察自主联想、尝试内心独白；工具可以增强，Core动力学缺口只能报告后讨论。

由此另立E44，不再把当前Qwen的成功设为所有从零路线的前置条件。旧E42判据和E43结果不改。允许外设学习表达与表示，正式新经历归因阶段固定外设及缓存。物理/模拟背景与无外界刺激分开，无新语言期间的活动和杂乱译文完整保存。此条为决定与执行登记，未预告语言已经成功。

[计划、讨论和原话](../../plans/language-development.md) · [E44登记](../../../../lab/explorations/2026-10-04-language-development/design.zh.md)""",
        "en": """### 2026-10-04: independent scratch-language co-development

After E43 preserved structure without reliable new-pair retrieval/expression, the researcher asked whether jointly developed small Transformers, embodied experience and social interaction could support continually learned language. The assistant separated input, retrieval, relational composition and expression, recommending grounded co-development before social communication and longer evolution. The user approved execution, continuous observation of internal associations and attempted monologue interpretation, permitting new tools but requiring discussion before changing Core dynamics.

E44 therefore removes current Qwen success as a prerequisite for every scratch route, without rewriting E42 criteria or E43 results. Adapters may learn representations and expression; freeze them and their cache boundaries for new-experience attribution. Distinguish background-supported intervals from no external input; retain all activity and raw, possibly disordered text. This is a decision and registration, not a language success claim.

[Roadmap and dialogue](../../plans/language-development.md) · [E44 registration](../../../../lab/explorations/2026-10-04-language-development/design.en.md)"""
    }
    for language, entry in entries.items():
        append(f"docs/{language}/history/chronicles/07-priority-experiments.md", entry)
        append(f"docs/{language}/history/themes/02-instruments.md", entry)
        append(f"docs/{language}/history/sources/source-register.md", entry.replace("../../plans/", "../../plans/"))
        append(f"docs/{language}/plans/scratch-language-centre.md",
               "### 2026-10-04：后续顺序更新 / Subsequent execution-order revision\n\n"
               "[共同发育路线 / Co-development](language-development.md) 已获用户批准。当前Qwen成功不再是新路线的前置条件；上文旧批次门槛与结果保持原义。 / The user approved the independent route; current Qwen success no longer gates it. Earlier criteria and results above retain their original meaning.")
        append(f"docs/{language}/plans/index.md", "- [语言共同发育 / Language co-development](language-development.md)：E44，独立感官校准、从零训练与连续内部活动转译。")
        append(f"docs/{language}/history/milestones.md", "| 2026-10-04 | E44从零语言共同发育获准 / Scratch language co-development approved | [Plan](../plans/language-development.md)；旧Core与旧证据不改 / Core and earlier evidence preserved |")
        backlog = ROOT / f"docs/{language}/plans/research-backlog.md"
        text = backlog.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("| R17 /"):
                lines[i] = ("| R17 / 当前优先，E44已登记 | 从零Transformer与ThreeMind共同发育，持续转译联想 | E42–E43结果保留，Qwen成功不再是从零路线前置；工具/新试验正在推进 | 先校准，再冻结外设测试新对应和连续活动；内核缺口仅报告 | [E44计划](language-development.md)，结果未定 |"
                            if language == "zh" else
                            "| R17 / Active, E44 registered | Scratch Transformer co-development and continuous internal-activity interpretation | E42–E43 unchanged; current Qwen success no longer gates the scratch route; tooling/experiments underway | Calibrate then freeze adapters for new associations and unprompted activity; report Core gaps without altering dynamics | [E44 plan](language-development.md); results pending |")
                break
        backlog.write_text("\n".join(lines) + "\n", encoding="utf-8")
        append(f"docs/{language}/plans/research-backlog.md", entry.replace("../../plans/language-development.md", "language-development.md").replace("../../../../lab/", "../../../lab/"))
    classical = """### 2026年10月4日：语言共育之议

既试间习，迹留而问之未能达。研究者曰：识能因历而变，何不与小型语言之器共育？又当察其内联，虽言杂亦录之。遂立新试，不以旧器成败限诸新途；核法仍旧，感、忆、述各考其失。先授同见之物，后究相告之用，地球演化之长程则后议。此记立议，未称功成。

[原议与授权](../../plans/language-development.md)"""
    append("docs/zh/history/classical/shiji-05.md", classical)
    append("docs/zh/history/classical/tongjian-04.md", classical)


if __name__ == "__main__":
    main()
