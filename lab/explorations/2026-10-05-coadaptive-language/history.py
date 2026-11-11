"""Append the completed E52 interpretation, preserving earlier records."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def append(path, text):
    file = ROOT/path
    previous = file.read_text(encoding='utf-8')
    if text.strip() not in previous:
        file.write_text(previous.rstrip()+'\n\n'+text.strip()+'\n', encoding='utf-8')


def main():
    result = json.loads((HERE/'conclusions.json').read_text(encoding='utf-8'))
    for lang in ('zh', 'en'):
        zh = lang == 'zh'
        summary = result['summary_'+lang]
        body = result['history_'+lang]
        file = ROOT/f'docs/{lang}/plans/research-backlog.md'
        text = file.read_text(encoding='utf-8')
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('**E52'):
                lines[i] = f'**{summary}** [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.{lang}.md)'
            elif line.startswith('| R17 /'):
                lines[i] = ('| R17 / E52阶段完成，继续 | 局部表达、共同所指与回答归属 | E50已教命名及通路证据保留；E52共同学习、只转写和时间校准对照已做 | 自然交流和新经历的忠实翻译仍未完成，不将外设监督答题等同Core内容 | [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.zh.md) |' if zh else
                    '| R17 / E52 phase complete, continuing | Local expression and attribution | E50 naming/pathway evidence retained; E52 coadaptation, transcription-only and context-calibration controls completed | Faithful new-experience translation and natural conversation remain open; supervised peripheral answers are not Core content | [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md) |')
            elif line.startswith('| T07 /'):
                lines[i] = ('| T07 / 工具阶段完成，继续 | 个人可塑语言外设 | 持续训练、有界回放、快照、Python/CLI、原话自听、CPU/CUDA小型验证完成 | [工具](../reference/adaptive-expression.md)；实际发射流对照、生产聊天UI仍未完成 |' if zh else
                    '| T07 / tooling phase complete, continuing | Personal adaptive language peripheral | Continued weights, bounded replay, checkpoints, Python/CLI, exact self-hearing and small CPU/CUDA checks delivered | [Tool](../reference/adaptive-expression.md); emitted-stream comparison and production chat UI remain open |')
        if not any(line.startswith('| C30 |') for line in lines):
            index = next(i for i, line in enumerate(lines) if line.startswith('| C29 |'))
            lines.insert(index+1, ('| C30 | E52共同学习与严格翻译对照 | '+summary+' | [报告](../../../lab/explorations/2026-10-05-coadaptive-language/report.zh.md) |' if zh else
                '| C30 | E52 coadaptation and strict translation controls | '+summary+' | [Report](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md) |'))
        if not any(line.startswith('| R33 /') for line in lines):
            index = next(i for i, line in enumerate(lines) if line.startswith('| R32 /'))
            lines.insert(index+1, ('| R33 / P1 后续待议 | 只负责翻译、随个体变化的语言外设 | 工程共同学习已能运行，忠实翻译仍需定位；避免把问答标签记入外设后当作Core知识 | 区分直接听词、联想词、表达通道；跨时间、反向经历、固定外设干预验证；不再盲目扩大课程 | [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.zh.md) |' if zh else
                '| R33 / P1 next phase to discuss | Faithful adaptive translation | Engineering loop runs; task-label supervision must not substitute for Core knowledge | Separate heard, recalled and expressed-word activity; test across time, reversed experience and fixed-head interventions before larger courses | [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md) |'))
        file.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md', f'### 2026-10-05: E52\n\n{summary}\n\n[Report](../../../lab/explorations/2026-10-05-coadaptive-language/report.{lang}.md)')
        for name in ('chronicles/07-priority-experiments.md', 'themes/02-instruments.md', 'sources/source-register.md'):
            title = '共同塑造语言外设，分清翻译与答题' if zh else 'Coadaptive language: translation versus answering'
            append(f'docs/{lang}/history/{name}', f'### 2026-10-05：E52 {title}\n\n{body}\n\n[原话与决定 / Dialogue and decision](../../plans/coadaptive-language-center.md) · [报告 / Report](../../../../lab/explorations/2026-10-05-coadaptive-language/report.{lang}.md)')
        append(f'docs/{lang}/history/milestones.md', f'2026-10-05 — {summary} [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.{lang}.md)')
        append(f'docs/{lang}/plans/coadaptive-language-center.md', f'## 2026-10-05：阶段交付 / Phase delivery\n\n{summary}\n\n[Report](../../../lab/explorations/2026-10-05-coadaptive-language/report.{lang}.md)')
    append('docs/zh/history/classical/shiji-05.md', '### 译者不代思\n\n用户复言，所谓多角度，乃一物见于诸句，非惟移目而视；又愿译者传其所发，不代其答。遂令核与个人译器并受教，所言仍从感官返听，另设但习词音、不授物名之器。习例虽可熟，后问仍多失；不学之核亦可借外器应答。继以简器读同迹，两源各试四词皆中，旧器各中其一，乃知听词之迹非不可读也；然联想之辞犹未能明。故分记习得、译得与何所自来，不以一数蔽之。所得器用存而续用，核法旧据皆不更；其能忠译新意，仍待求之。')
    append('docs/zh/history/classical/tongjian-04.md', '### 2026年10月5日：并教核与译器\n\n行E52，交色与形为四物，教其名，益新物，复更旧名。译器随教而学，亦可反听其言；设不反听、不塑核及但转写诸对照。又虑时迁而取象异，另校同刻之副本。转写不工，改以简器读同迹，两源各四试皆中，旧器各一中；但所中乃听词，非已明其联想。既记实测于册，不以习例皆中谓意识善言，不因译器失言便谓核中无迹。通用接口、原言、原迹与个人译器悉存，未来忠译之试另议。')


if __name__ == '__main__':
    main()
