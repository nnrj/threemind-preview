"""Offline, shared content model for Markdown, HTML, Word and PDF research exports."""

import base64
import io
import json
import math
import os
import re
import threading
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from functools import lru_cache
from html import escape
from pathlib import Path
from tempfile import SpooledTemporaryFile

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

from .evidence import SPOOL_BYTES

RENDER_LOCK = threading.Lock()  # Matplotlib/font registration have process-global caches.
MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"]).use(dollarmath_plugin)


def choose(zh, en, language):
    return en if language == "en" else zh


def value(raw, language="zh-CN"):
    if raw is None:
        return choose("缺失", "Missing", language)
    if isinstance(raw, float):
        return repr(raw)  # Round-trip precision; no silent small-value-to-zero conversion.
    return str(raw)


def report_font():
    configured = os.environ.get("THREEMIND_REPORT_FONT")
    paths = (
        [configured]
        if configured
        else [
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
    )
    for path in paths:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise ValueError(
        "缺少导出中文字体；安装 fonts-wqy-microhei，或设置 THREEMIND_REPORT_FONT 为支持中文的 TrueType 字体。"
    )


def capability():
    try:
        import docx  # noqa: F401
        import mathml2omml  # noqa: F401
        import reportlab  # noqa: F401
        import svglib  # noqa: F401
        import ziamath  # noqa: F401

        report_font()
        return {
            "name": "研究文档导出",
            "state": "available",
            "reason": "支持固定修订的 Markdown、HTML、Word、PDF 与证据包。",
        }
    except (ImportError, ValueError) as exc:
        return {"name": "研究文档导出", "state": "unavailable", "reason": str(exc)}


@lru_cache(maxsize=128)
def equation(latex, display=False):
    import latex2mathml.converter
    import mathml2omml
    import ziamath

    if len(latex) > 10000:
        raise ValueError("单个公式超过 10000 字符；请拆分公式。")
    try:
        mathml = latex2mathml.converter.convert(latex, display="block" if display else "inline")
        tree = ET.fromstring(mathml)
        if len(list(tree.iter())) > 5000 or any("\\" in (element.text or "") for element in tree.iter()):
            raise ValueError("unsupported or overly complex math command")
        # svglib does not implement SVG2 symbol/use sizing; explicit paths preserve glyph geometry.
        ziamath.config.svg2 = False
        svg = ziamath.Math(mathml, size=16, title=latex).svg()
        # The conversion library returns an OMML fragment whose m prefix is supplied here.
        omml = mathml2omml.convert(mathml)
        return mathml, svg, omml
    except Exception as exc:
        raise ValueError(
            f"公式无法可靠导出：{latex[:100]}。可先导出保留 LaTeX 的 Markdown。{type(exc).__name__}"
        ) from exc


def inline_html(tokens, *, pdf=False):
    parts = []
    tags = {"strong": "b", "em": "i", "s": "strike"}
    for token in tokens or []:
        if token.type in ("text", "html_inline"):
            parts.append(escape(token.content))
        elif token.type == "image":
            parts.append(escape(token.content))  # Never request arbitrary external images.
        elif token.type in ("softbreak", "hardbreak"):
            parts.append("<br/>" if pdf or token.type == "hardbreak" else "\n")
        elif token.type == "code_inline":
            parts.append(escape(token.content) if pdf else f"<code>{escape(token.content)}</code>")
        elif token.type == "math_inline":
            _, svg, _ = equation(token.content)
            parts.append(svg)
        elif token.type == "link_open":
            href = token.attrGet("href") or ""
            if href.startswith(("https://", "http://")):
                parts.append(f'<a href="{escape(href, quote=True)}">')
            else:
                parts.append("<span>" if not pdf else "")
        elif token.type == "link_close":
            # MarkdownIt validates schemes; non-http links deliberately remain plain text.
            previous = next((p for p in reversed(parts) if p.startswith(("<a ", "<span>"))), "")
            parts.append("</a>" if previous.startswith("<a ") else "</span>" if not pdf else "")
        elif token.tag in tags:
            tag = tags[token.tag]
            parts.append(f"<{tag}>" if token.nesting == 1 else f"</{tag}>")
    return "".join(parts)


def markdown_nodes(text):
    """Parse once without raw HTML, preserving lists, tables, code and math."""
    tokens, nodes, i = MARKDOWN.parse(text), [], 0
    lists, prefix = [], ""
    while i < len(tokens):
        token = tokens[i]
        if token.type in ("bullet_list_open", "ordered_list_open"):
            lists.append({"ordered": token.type == "ordered_list_open", "next": int(token.attrGet("start") or 1)})
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif token.type == "list_item_open":
            item = lists[-1]
            prefix = f"{item['next']}. " if item["ordered"] else "• "
            item["next"] += 1
        elif token.type in ("heading_open", "paragraph_open"):
            children = tokens[i + 1].children or []
            nodes.append(
                {
                    "type": "heading" if token.type == "heading_open" else "paragraph",
                    "level": min(4, int(token.tag[1]) + 1) if token.type == "heading_open" else len(lists),
                    "tokens": children,
                    "prefix": prefix,
                }
            )
            prefix = ""
            i += 2
        elif token.type in ("fence", "code_block"):
            nodes.append({"type": "code", "text": token.content})
        elif token.type.startswith("math_block"):
            nodes.append({"type": "math", "text": token.content})
        elif token.type == "table_open":
            rows, row = [], []
            while i < len(tokens) and tokens[i].type != "table_close":
                if tokens[i].type == "inline":
                    row.append(tokens[i].children or [])
                elif tokens[i].type == "tr_close":
                    rows.append(row)
                    row = []
                i += 1
            nodes.append({"type": "table", "rows": rows, "token_cells": True})
        elif token.type == "hr":
            nodes.append({"type": "paragraph", "text": ""})
        i += 1
    return nodes


def chart_assets(block, language):
    import matplotlib as mpl
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.font_manager import FontProperties

    font = FontProperties(fname=report_font(), size=9)
    data, chart = block["data"], block["chart"]
    rows, method = data["rows"], data["method"]
    figure = Figure(figsize=(7.1, 3.7), dpi=220, layout="constrained")
    FigureCanvasAgg(figure)
    ax = figure.subplots()
    green, amber = "#21796a", "#987044"
    if chart == "histogram":
        x = np.arange(len(rows))
        ax.bar(x, [r["count"] for r in rows], color=green, width=0.95)
        step = max(1, math.ceil(len(rows) / 7))
        low = rows[0]["lower"] if rows else 0
        span = rows[-1]["upper"] - low if rows else 0
        offset = low if span > 0 and abs(low) > span * 1000 else 0
        boundaries = {r[key] - offset for r in rows for key in ("lower", "upper")}
        precision = next(
            digits for digits in range(6, 18) if len({f"{v:.{digits}g}" for v in boundaries}) == len(boundaries)
        )
        ax.set_xticks(
            x[::step],
            [f"{r['lower'] - offset:.{precision}g}\n– {r['upper'] - offset:.{precision}g}" for r in rows[::step]],
        )
        ax.set_ylabel(choose("计数", "Count", language))
        caption = f"{block['metric']} ({data['unit']})"
        if offset:
            caption += "\n" + choose("分组边界为相对", "Bin boundaries are offsets from", language) + f" {offset!r}"
        ax.set_xlabel(caption)
    elif chart == "bar":
        values = [r["value"] if r["value"] is not None else np.nan for r in rows]
        if method == "all-events-by-kind-and-phase/1":
            from matplotlib.ticker import MaxNLocator

            figure.set_size_inches(7.1, max(3.7, len(rows) * 0.3 + 1))
            ax.barh(range(len(rows)), values, color=green)
            ax.set_yticks(range(len(rows)), [r["label"] + " / " + r["phase"] for r in rows])
            ax.invert_yaxis()
            ax.set_xlabel(data["unit"])
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        else:
            ax.bar(range(len(rows)), values, color=green)
            ax.set_xticks(range(len(rows)), [r["label"] for r in rows])
            ax.set_ylabel(data["unit"])
    else:
        binned = method == "ordinal-bin-sample-mean-min-max/1"
        first = int((rows[0].get("from_us") if binned else rows[0].get("time_us")) or 0) if rows else 0
        xs = [
            ((int(r["from_us"]) - first) + (int(r["through_us"]) - int(r["from_us"])) / 2) / 1e6
            if binned
            else (int(r["time_us"]) - first) / 1e6
            for r in rows
        ]
        ys = [r["value"] if r["value"] is not None else np.nan for r in rows]
        label = choose("样本均值", "Sample mean", language) if binned else block["metric"]
        if chart == "scatter":
            ax.scatter(xs, ys, color=green, s=8, label=label)
        else:
            ax.plot(xs, ys, color=green, linewidth=1.4, label=label)
        if binned:
            for key, label in (
                ("minimum", choose("最小值", "Minimum", language)),
                ("maximum", choose("最大值", "Maximum", language)),
            ):
                ax.plot(
                    xs,
                    [r[key] if r[key] is not None else np.nan for r in rows],
                    color=amber,
                    linestyle="--",
                    linewidth=0.7,
                    label=label,
                )
            missing = [(x, y) for x, y, r in zip(xs, ys, rows) if r["count"] < r["total"] and r["value"] is not None]
            if missing:
                ax.scatter(
                    *zip(*missing),
                    marker="^",
                    s=24,
                    color="#b45f50",
                    label=choose("含缺失值", "Contains missing values", language),
                )
            ax.legend(prop=font, fontsize=8, loc="best")
        ax.set_xlabel(choose("相对首个样本的时间", "Time since first sample", language) + f" (s)\n{first} μs")
        ax.set_ylabel(data["unit"])
    ax.grid(axis="y", alpha=0.17)
    ax.spines[["top", "right"]].set_visible(False)
    for label in [
        ax.xaxis.label,
        ax.yaxis.label,
        *ax.get_xticklabels(),
        *ax.get_yticklabels(),
        ax.xaxis.get_offset_text(),
        ax.yaxis.get_offset_text(),
    ]:
        label.set_fontproperties(font)
    buffers = {}
    with mpl.rc_context({"svg.fonttype": "path", "svg.hashsalt": "threemind-research-export-1"}):
        for extension in ("svg", "png"):
            stream = io.BytesIO()
            figure.savefig(stream, format=extension, metadata={"Date": None} if extension == "svg" else {})
            buffers[extension] = stream.getvalue()
    figure.clear()
    return buffers


def content_nodes(document, rendered, options):
    language, assets, nodes, warnings = options["language"], {}, [], []
    tr = lambda zh, en: choose(zh, en, language)

    def paragraph(text, muted=False):
        nodes.append({"type": "paragraph", "text": text, "muted": muted})

    nodes.append({"type": "title", "text": document["spec"]["title"]})
    paragraph(
        tr(
            "实验记录" if document["kind"] == "record" else "实验报告",
            "Experiment record" if document["kind"] == "record" else "Experiment report",
        )
        + f" · r{document['content_revision']} · {document['review']}",
        True,
    )
    paragraph(tr("文档 SHA256 ", "Document SHA256 ") + document["content_hash"], True)
    if document.get("ai_call_id"):
        paragraph(
            tr(
                "含 AI 辅助生成内容；复核状态以上述修订为准。生成调用 ",
                "Contains AI-assisted content; the review status applies to this revision. Generation call ",
            )
            + str(document["ai_call_id"]),
            True,
        )
    elif document.get("import_ai_generated"):
        paragraph(
            tr(
                "含 AI 辅助生成内容；标识来自导入记录，复核状态以本修订为准。",
                "Contains AI-assisted content; provenance comes from the imported record. The review status applies to this revision.",
            ),
            True,
        )
    section_titles = {
        "purpose": ("研究目的", "Purpose"),
        "methods": ("方法与过程", "Methods"),
        "results": ("观测结果", "Results"),
        "discussion": ("讨论", "Discussion"),
        "limitations": ("限制与缺失", "Limitations"),
        "hypothesis": ("研究假说", "Hypothesis"),
        "other": ("其他说明", "Commentary"),
    }

    def block_nodes(block):
        kind = block["type"]
        if kind == "record_block":
            paragraph(
                tr("引用实验记录 ", "Referenced record ")
                + f"{block['record_id']} r{block['revision']} · {block['block_id']}",
                True,
            )
            paragraph("SHA256 " + block["record_hash"], True)
            if block.get("record_ai_call_id"):
                paragraph(
                    tr(
                        "引用记录含 AI 辅助生成内容；生成调用 ",
                        "Referenced record contains AI-assisted content; generation call ",
                    )
                    + block["record_ai_call_id"],
                    True,
                )
            elif block.get("record_import_ai_generated"):
                paragraph(
                    tr(
                        "引用记录含 AI 辅助生成内容；标识来自导入记录。",
                        "Referenced record contains AI-assisted content; provenance comes from the imported record.",
                    ),
                    True,
                )
            block_nodes(block["content"])
        elif kind == "commentary":
            nodes.append({"type": "heading", "level": 1, "text": tr(*section_titles[block["section"]])})
            paragraph(tr("作者说明与解释", "Author commentary and interpretation"), True)
            nodes.append({"type": "markdown", "text": block["markdown"]})
        elif kind == "fact":
            nodes.append(
                {
                    "type": "heading",
                    "level": 2,
                    "text": block.get("label") or f"{block['metric']} · {block['statistic']}",
                }
            )
            paragraph(f"{value(block['value'], language)} {block['unit']}")
            paragraph(
                f"{tr('有效样本', 'Valid samples')} {block['statistics']['count']}; {tr('缺失', 'Missing')} {block['statistics']['missing']}",
                True,
            )
        elif kind == "assessment_summary":
            nodes.append({"type": "heading", "level": 2, "text": tr("固定规则判定", "Frozen criterion decisions")})
            paragraph(
                tr(
                    "所有已声明试验均计入分母；缺失和未完成保留未判定。比例上下界不是置信区间，结论只适用于已声明测试集。",
                    "Every declared trial stays in the denominator. Missing and unfinished results remain undetermined. Fraction bounds are not confidence intervals; decisions apply only to the declared test set.",
                )
            )
            decisions = {
                "satisfied": tr("符合", "Satisfied"),
                "not_satisfied": tr("不符合", "Not satisfied"),
                "undetermined": tr("未判定", "Undetermined"),
            }
            for item in block["assessment"]["criteria"]:
                rule = item["criterion"]
                nodes.append({"type": "heading", "level": 3, "text": rule["id"] + " · " + decisions[item["status"]]})
                paragraph(
                    f"{rule['metric']} {rule['operator']} {value(rule['threshold'])}; {tr('要求比例', 'Required fraction')} {value(rule['required_fraction'])}"
                )
                nodes.append(
                    {
                        "type": "table",
                        "token_cells": False,
                        "column_weights": [1, 1, 1, 1],
                        "rows": [
                            [
                                tr("试验总数", "Declared trials"),
                                tr("符合", "Satisfied"),
                                tr("不符合", "Not satisfied"),
                                tr("未判定", "Undetermined"),
                            ],
                            [str(item[key]) for key in ("total", "satisfied", "not_satisfied", "undetermined")],
                        ],
                    }
                )
                paragraph(
                    f"{tr('比例上下界', 'Fraction bounds')}: {value(item['fraction_lower_bound'])} .. {value(item['fraction_upper_bound'])}"
                )
            paragraph(tr("固定来源 ", "Fixed source ") + block["source"] + " · SHA256 " + block["source_hash"], True)
        elif kind == "chart":
            number = 1 + sum(name.endswith(".png") for name in assets)
            prefix = f"figures/figure-{number:03}"
            outputs = chart_assets(block, language)
            for extension, raw in outputs.items():
                assets[f"{prefix}.{extension}"] = raw
            title = f"{tr('图', 'Figure')} {number} " + (block.get("title") or block["metric"])
            nodes.append({"type": "heading", "level": 2, "text": title})
            nodes.append({"type": "figure", "png": prefix + ".png", "svg": prefix + ".svg", "title": title})
            stats = block["data"]["statistics"]
            caption = [
                f"{block['data']['method']} · {tr('有效样本', 'Valid samples')} {stats['count']}; {tr('缺失', 'Missing')} {stats['missing']}"
            ]
            if block["data"]["method"] == "ordinal-bin-sample-mean-min-max/1":
                caption.append(
                    tr(
                        "显示分组为样本均值及最小值、最大值；此范围不是置信区间。三角形标识含缺失值的分组。",
                        "Display bins show sample means and minima/maxima, not confidence intervals. Triangles mark bins containing missing values.",
                    )
                )
            caption.append(tr("固定来源 ", "Fixed source ") + block["source"])
            paragraph("\n".join(caption), True)
            nodes[-1]["keep_together"] = True
        elif kind == "table":
            nodes.append({"type": "heading", "level": 2, "text": block.get("title") or tr("数据表格", "Data table")})
            selected, total = len(block["rows"]), block["row_count"]
            paragraph(
                tr(
                    f"正文展示前 {selected} 行，固定来源共 {total} 行。",
                    f"Body includes the first {selected} of {total} captured rows.",
                ),
                True,
            )
            if selected < total:
                warnings.append(
                    {"block_id": block["id"], "kind": "table_excerpt", "included": selected, "total": total}
                )
            if rendered["sources"][block["source"]]["manifest"]["kind"] == "events":
                paragraph(
                    tr(
                        "事件时间为模拟时间，受理时间为宿主机 UTC；二者不能直接相减。计数单位是日志条目，不能当作独立实验。正文不展开原始载体与参数，完整内容可随证据包导出。",
                        "Event time is simulation time; admission time is host UTC. Do not subtract these clocks. Counts are log entries, not independent experiments. Raw carriers and parameters can be included in the evidence package.",
                    ),
                    True,
                )
                rows = [
                    [
                        tr("序号 / 事件 ID", "Ordinal / event ID"),
                        tr("模拟时间 μs / 版本", "Time μs / revision"),
                        tr("类型 / 阶段", "Kind / phase"),
                        tr("事件键", "Event key"),
                    ]
                ]
                audit = [
                    [
                        tr("序号", "Ordinal"),
                        tr("命令 / 受理时间 UTC", "Command / admitted UTC"),
                        tr("原始内容 SHA-256", "Raw content SHA-256"),
                    ]
                ]
                for r in block["rows"]:
                    p = r["provenance"]
                    rows.append(
                        [
                            str(r["ordinal"]) + " / " + p["event_id"],
                            r["time_us"] + " / r" + str(p["commit_revision"]),
                            r["label"] + " / " + r["quality"],
                            p["event_key"],
                        ]
                    )
                    audit.append(
                        [
                            str(r["ordinal"]),
                            (p["command_id"] or "—") + " / " + (p["admitted_at"] or "—"),
                            p["payload_hash"],
                        ]
                    )
                nodes.extend(
                    [
                        {"type": "table", "rows": rows, "token_cells": False, "column_weights": [1.6, 3, 6, 6.6]},
                        {"type": "table", "rows": audit, "token_cells": False, "column_weights": [1.2, 6.2, 9.8]},
                    ]
                )
                paragraph(tr("固定来源 ", "Fixed source ") + block["source"], True)
                return
            # Wide metric tables are split into readable panels with the same stable row identity.
            trajectory = rendered["sources"][block["source"]]["manifest"]["kind"] == "trajectory"

            def identity(row):
                if trajectory:
                    return value(row["time_us"], language)
                return str(row["label"]) + (f"\n{row['time_us']} μs" if row["time_us"] is not None else "")

            for start in range(0, len(block["metrics"]), 3):
                metrics = block["metrics"][start : start + 3]
                header = [
                    tr("序号", "Ordinal"),
                    tr("模拟时间 μs", "Time μs") if trajectory else tr("对象 / 模拟时间", "Object / simulation time"),
                    tr("质量", "Quality"),
                    *metrics,
                ]
                rows = [header] + [
                    [
                        str(r["ordinal"]),
                        identity(r),
                        r["quality"],
                        *[value(r["values"].get(metric), language) for metric in metrics],
                    ]
                    for r in block["rows"]
                ]
                nodes.append({"type": "table", "rows": rows, "token_cells": False})
        if kind in ("table", "fact"):
            paragraph(tr("固定来源 ", "Fixed source ") + block["source"], True)

    for block in rendered["blocks"]:
        block_nodes(block)
    nodes.append({"type": "heading", "level": 1, "text": tr("来源与数据范围", "Sources and data coverage")})
    paragraph(
        tr(
            "缺失值保留为空；单条轨迹的时间采样不等于独立重复实验，样本均值也不等于时间加权均值。",
            "Missing values remain null. Time samples from one trajectory are not independent experimental replicates; sample means are not time-weighted means.",
        )
    )
    paragraph(
        tr(
            "证据包包含完整来源清单、文档 JSON、图表 SVG 和 PNG。"
            + ("已附带所有固定来源的数据行。" if options["include_data"] else "本次未附带完整数据行。"),
            "The evidence package contains complete source manifests, document JSON, SVG and PNG figures. "
            + (
                "All captured data rows are included."
                if options["include_data"]
                else "Complete data rows are not included."
            ),
        )
    )
    for key, source in rendered["sources"].items():
        manifest = source["manifest"]
        nodes.append({"type": "heading", "level": 2, "text": f"{manifest['kind']} · {key}"})
        paragraph("SHA256 " + source["content_hash"], True)
        for label, obj in (
            (tr("选取范围", "Selection"), manifest.get("selection")),
            (tr("覆盖与缺失", "Coverage and missing values"), manifest.get("coverage")),
        ):
            if obj:
                paragraph(label)
                for k, val in obj.items():
                    paragraph(f"{k}: {json.dumps(val, ensure_ascii=False, allow_nan=False)}", True)
        if manifest.get("analysis"):
            analysis = manifest["analysis"]
            for key in ("method", "unit", "seed", "resamples", "warnings"):
                if key in analysis:
                    paragraph(f"{key}: {json.dumps(analysis[key], ensure_ascii=False)}", True)
        provenance = manifest.get("provenance", {})
        for k in ("run_name", "run_id", "checkpoint", "protocol_hash", "artifact_id", "artifact_hash"):
            if provenance.get(k) is not None:
                paragraph(f"{k}: {json.dumps(provenance[k], ensure_ascii=False)}", True)
    return nodes, assets, warnings


def markdown_output(nodes):
    lines = []
    for node in nodes:
        kind = node["type"]
        if "tokens" in node:
            # Inline Markdown tokens retain source text through their markup and children.
            text = "".join(
                token.markup
                if token.nesting
                else f"${token.content}$"
                if token.type == "math_inline"
                else f"`{token.content}`"
                if token.type == "code_inline"
                else token.content
                if token.type not in ("softbreak", "hardbreak")
                else "\n"
                for token in node["tokens"]
            )
            text = node.get("prefix", "") + text
        else:
            text = node.get("text", "")
        if kind in ("title", "heading"):
            lines.append("#" * (1 if kind == "title" else min(6, node.get("level", 1) + 1)) + " " + text)
        elif kind in ("paragraph", "markdown"):
            lines.append(text)
        elif kind == "code":
            fence = "`" * max(3, max((len(m[0]) for m in re.finditer(r"`+", text)), default=0) + 1)
            lines.append(f"{fence}\n{text}\n{fence}")
        elif kind == "math":
            lines.append(f"$$\n{text}\n$$")
        elif kind == "figure":
            lines.append(f"![{node['title'].replace(']', '')}](./{node['png']})")
        elif kind == "table":

            def cell(raw, token_cells=node["token_cells"]):
                text = "".join(t.content for t in raw if not t.nesting) if token_cells else raw
                return str(text).replace("|", "\\|").replace("\n", "<br>")

            rows = ["| " + " | ".join(cell(c) for c in row) + " |" for row in node["rows"]]
            if rows:
                rows.insert(1, "| " + " | ".join("---" for _ in node["rows"][0]) + " |")
            lines.append("\n".join(rows))
    return ("\n\n".join(lines) + "\n").encode()


def html_output(nodes, assets, title, language):
    pieces = []
    for node in nodes:
        kind = node["type"]
        content = escape(node.get("prefix", "")) + (
            inline_html(node["tokens"]) if "tokens" in node else escape(node.get("text", ""))
        )
        if kind in ("title", "heading"):
            tag = "h1" if kind == "title" else f"h{min(6, node.get('level', 1) + 1)}"
            pieces.append(f"<{tag}>{content}</{tag}>")
        elif kind == "paragraph":
            cls = "muted" if node.get("muted") else ""
            pieces.append(f'<p class="{cls}">{content}</p>')
        elif kind == "code":
            pieces.append(f"<pre><code>{content}</code></pre>")
        elif kind == "math":
            pieces.append(f'<div class="equation">{equation(node["text"], True)[1]}</div>')
        elif kind == "figure":
            encoded = base64.b64encode(assets[node["svg"]]).decode()
            pieces.append(
                f'<figure><img alt="{escape(node["title"], quote=True)}" src="data:image/svg+xml;base64,{encoded}"></figure>'
            )
        elif kind == "table":
            rows = []
            for i, row in enumerate(node["rows"]):
                tag = "th" if i == 0 else "td"
                rows.append(
                    "<tr>"
                    + "".join(
                        f"<{tag}>{inline_html(c) if node['token_cells'] else escape(str(c))}</{tag}>" for c in row
                    )
                    + "</tr>"
                )
            if rows:
                pieces.append(
                    f'<div class="table-wrap" tabindex="0"><table><thead>{rows[0]}</thead><tbody>{"".join(rows[1:])}</tbody></table></div>'
                )
    css = """body{font:15px/1.65 'Microsoft YaHei','Noto Sans CJK SC',sans-serif;color:#171b19;margin:40px auto;padding:0 24px;max-width:880px}h1,h2,h3,h4{color:#000;line-height:1.3;break-after:avoid}h1{font-size:29px}h2{margin-top:34px;font-size:21px}h3{font-size:17px}p,td,th{overflow-wrap:anywhere}.muted{color:#53605a;font-size:12px}figure{margin:16px 0;break-inside:avoid}figure img{width:100%;height:auto}p svg{height:1.4em;width:auto;vertical-align:middle}.equation{padding:15px 0;text-align:center;overflow:auto}.equation svg{max-width:100%;height:auto}table{width:100%;border-collapse:collapse;font-size:12px;margin:12px 0 22px}th,td{padding:8px 10px;border:1px solid #d9d9d9;text-align:left}th{background:#36463e;color:#fff}tbody tr:nth-child(even){background:#f4f6f5}thead{display:table-header-group}.table-wrap{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f6;padding:14px}a{color:#1a7564}@media print{@page{size:A4;margin:18mm}body{margin:0;padding:0;max-width:none}h1{font-size:24px}.table-wrap{overflow:visible}tr{break-inside:avoid}}"""
    css += "@media screen and (max-width:600px){body{margin:24px auto;padding:0 16px}.table-wrap table{min-width:560px}.table-wrap::before{content:'↔';color:#53605a;font-size:16px}}"
    return (
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'\">"
        f"<title>{escape(title)}</title><style>{css}</style></head><body>{''.join(pieces)}</body></html>"
    ).encode()


@contextmanager
def publication(document, rendered, options):
    with SpooledTemporaryFile(max_size=SPOOL_BYTES, mode="w+b") as output:
        with RENDER_LOCK:
            nodes, assets, warnings = content_nodes(document, rendered, options)
            fmt = options["format"]
            if fmt != "markdown":
                nodes = [
                    part
                    for node in nodes
                    for part in (markdown_nodes(node["text"]) if node["type"] == "markdown" else [node])
                ]
            if fmt == "markdown":
                output.write(markdown_output(nodes))
            elif fmt == "html":
                output.write(html_output(nodes, assets, document["spec"]["title"], options["language"]))
            else:
                from .report_layout import pdf_document, word_document

                (word_document if fmt == "docx" else pdf_document)(nodes, assets, output, document, options)
        # Streaming a large evidence package must not hold the plotting/font lock.
        output.seek(0)
        extension, media_type = {
            "markdown": ("md", "text/markdown; charset=utf-8"),
            "html": ("html", "text/html; charset=utf-8"),
            "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "pdf": ("pdf", "application/pdf"),
        }[fmt]
        yield f"research-r{document['content_revision']}.{extension}", media_type, output, assets, warnings
