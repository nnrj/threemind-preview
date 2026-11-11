"""Paged research layouts with editable Word text, tables and native OMML math."""

import base64
import io
from html import escape

from .report_publication import equation, report_font


def word_document(nodes, assets, output, metadata, options):
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    document.core_properties.title = metadata["spec"]["title"]
    document.core_properties.author = "ThreeMind"
    document.core_properties.subject = f"revision {metadata['content_revision']}; SHA256 {metadata['content_hash']}"
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.8)
    section.left_margin = section.right_margin = Cm(1.9)
    east_asia = "Microsoft YaHei" if report_font().startswith("C:") else "WenQuanYi Micro Hei"
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        style = document.styles[name]
        style.font.name, style.font.color.rgb = "Arial", RGBColor(0, 0, 0)
        style.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), east_asia)
        for border in style.element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn("w:" + key), None)
        style.paragraph_format.space_after = Pt(7)
        style.paragraph_format.line_spacing = 1.2
    document.styles["Normal"].font.size = Pt(10)
    document.styles["Title"].font.size = Pt(24)
    document.styles["Title"].font.bold = False
    for level, size in ((1, 16), (2, 13), (3, 11), (4, 10)):
        style = document.styles[f"Heading {level}"]
        style.font.size, style.font.bold = Pt(size), True
        style.paragraph_format.space_before = Pt(15 if level == 1 else 10)
        style.paragraph_format.keep_with_next = True

    def add_math(paragraph, latex, display=False):
        omml = equation(latex, display)[2]
        root = parse_xml(f'<root xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">{omml}</root>')
        for element in list(root):
            paragraph._p.append(element)

    def inline(paragraph, tokens):
        flags = {"bold": False, "italic": False, "strike": False}
        link = None
        for token in tokens:
            if token.type == "math_inline":
                add_math(paragraph, token.content)
                continue
            if token.type == "link_open":
                href = token.attrGet("href") or ""
                if href.startswith(("https://", "http://")):
                    link = OxmlElement("w:hyperlink")
                    link.set(qn("r:id"), paragraph.part.relate_to(href, RT.HYPERLINK, is_external=True))
                    paragraph._p.append(link)
                continue
            if token.type == "link_close":
                link = None
                continue
            if token.tag in ("strong", "em", "s"):
                flags[{"strong": "bold", "em": "italic", "s": "strike"}[token.tag]] = token.nesting == 1
                continue
            if token.type not in ("text", "html_inline", "image", "code_inline", "softbreak", "hardbreak"):
                continue
            run = paragraph.add_run("\n" if token.type in ("softbreak", "hardbreak") else token.content)
            run.bold, run.italic, run.font.strike = flags["bold"], flags["italic"], flags["strike"]
            if token.type == "code_inline":
                run.font.name = "Consolas"
            if link is not None:
                run.font.color.rgb = RGBColor.from_string("1A7564")
                run.underline = True
                link.append(run._r)

    for node in nodes:
        kind = node["type"]
        if kind == "table":
            if not node["rows"]:
                continue
            count = max(map(len, node["rows"]))
            table = document.add_table(rows=0, cols=count)
            table.autofit = False
            widths = table_widths(node, 17.2)
            for column, width in zip(table.columns, widths):
                column.width = Cm(width)
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                border = OxmlElement(f"w:{edge}")
                for key, val in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                    border.set(qn(f"w:{key}"), val)
                borders.append(border)
            table._tbl.tblPr.append(borders)
            for i, row in enumerate(node["rows"]):
                cells = table.add_row().cells
                # Keep ordinary measurement rows intact across pages. Long authored rows may split.
                if not node["token_cells"] or all(sum(len(t.content) for t in cell) < 500 for cell in row):
                    table.rows[-1]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                if i == 0:
                    table.rows[-1]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                for j, raw in enumerate(row):
                    cell = cells[j]
                    cell.width = Cm(widths[j])
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    props = cell._tc.get_or_add_tcPr()
                    margins = OxmlElement("w:tcMar")
                    for edge in ("top", "left", "bottom", "right"):
                        margin = OxmlElement(f"w:{edge}")
                        margin.set(qn("w:w"), "90")
                        margin.set(qn("w:type"), "dxa")
                        margins.append(margin)
                    props.append(margins)
                    shade = OxmlElement("w:shd")
                    shade.set(qn("w:fill"), "36463E" if i == 0 else "F4F6F5" if i % 2 == 0 else "FFFFFF")
                    props.append(shade)
                    paragraph = cell.paragraphs[0]
                    paragraph.paragraph_format.space_after = Pt(2)
                    if node["token_cells"]:
                        inline(paragraph, raw)
                    else:
                        paragraph.add_run(str(raw))
                    if not node["token_cells"] and j != 2:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        run.font.size = Pt(8)
                        if i == 0:
                            run.bold, run.font.color.rgb = True, RGBColor(255, 255, 255)
            document.add_paragraph().paragraph_format.space_after = Pt(2)
            continue
        if kind == "figure":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            picture = paragraph.add_run().add_picture(io.BytesIO(assets[node["png"]]), width=Cm(16))
            picture._inline.docPr.set("descr", node["title"])
            continue
        style = (
            "Title" if kind == "title" else f"Heading {min(4, node.get('level', 1))}" if kind == "heading" else "Normal"
        )
        paragraph = document.add_paragraph(style=style)
        paragraph.paragraph_format.keep_together = bool(node.get("keep_together"))
        if kind == "math":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_math(paragraph, node["text"], True)
        elif "tokens" in node:
            paragraph.add_run(node.get("prefix", ""))
            if node.get("level", 0) and kind == "paragraph":
                paragraph.paragraph_format.left_indent = Cm(min(2, node["level"] * 0.4))
            inline(paragraph, node["tokens"])
        else:
            run = paragraph.add_run(node.get("text", ""))
            if node.get("muted"):
                run.font.size, run.font.color.rgb = Pt(8), RGBColor.from_string("53605A")
            if kind == "code":
                run.font.name, run.font.size = "Consolas", Pt(8)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    document.save(output)


def table_widths(node, width):
    count = max(map(len, node["rows"]))
    if node.get("column_weights"):
        weights = node["column_weights"]
        return [width * weight / sum(weights) for weight in weights]
    if not node["token_cells"] and count >= 4:
        return [1.2 / 17.2 * width, 3.4 / 17.2 * width, 2.8 / 17.2 * width] + [(width * 9.8 / 17.2) / (count - 3)] * (
            count - 3
        )
    return [width / count] * count


def pdf_document(nodes, assets, output, metadata, options):
    from reportlab.graphics import renderPM
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
    from svglib.svglib import svg2rlg

    family = "ThreeMindReport"
    if family not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(family, report_font(), subfontIndex=0))
        pdfmetrics.registerFontFamily(family, normal=family, bold=family, italic=family, boldItalic=family)
    width = A4[0] - 3.8 * cm
    body = ParagraphStyle("Body", fontName=family, fontSize=9.5, leading=15, spaceAfter=7, wordWrap="CJK")
    muted = ParagraphStyle("Muted", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#53605a"))
    title = ParagraphStyle("Title", parent=body, fontSize=22, leading=29, spaceAfter=13, keepWithNext=True)
    headings = {
        i: ParagraphStyle(
            f"Heading{i}",
            parent=body,
            fontSize=size,
            leading=size * 1.5,
            spaceBefore=14 if i == 1 else 10,
            spaceAfter=7,
            keepWithNext=True,
        )
        for i, size in ((1, 15), (2, 12), (3, 10.5), (4, 10))
    }
    cell_style = ParagraphStyle("Cell", parent=body, fontSize=7.5, leading=11, spaceAfter=0, wordWrap=None)
    head_style = ParagraphStyle("TableHeading", parent=cell_style, textColor=colors.white)

    def math_drawing(latex, display=False):
        return svg2rlg(io.BytesIO(equation(latex, display)[1].encode()))

    def inline(tokens):
        pieces, tags, links = [], {"strong": "b", "em": "i", "s": "strike"}, []
        for token in tokens:
            if token.type == "math_inline":
                drawing = math_drawing(token.content)
                png = renderPM.drawToString(drawing, fmt="PNG", dpi=300)
                encoded = base64.b64encode(png).decode()
                scale = min(1, width / drawing.width)
                pieces.append(
                    f'<img src="data:image/png;base64,{encoded}" width="{drawing.width * scale}" height="{drawing.height * scale}" valign="middle"/>'
                )
            elif token.type in ("text", "image", "html_inline", "code_inline"):
                pieces.append(escape(token.content))
            elif token.type in ("softbreak", "hardbreak"):
                pieces.append("<br/>")
            elif token.type == "link_open":
                href = token.attrGet("href") or ""
                allowed = href.startswith(("https://", "http://"))
                links.append(allowed)
                if allowed:
                    pieces.append(f'<a href="{escape(href, quote=True)}" color="#1a7564">')
            elif token.type == "link_close":
                if links.pop():
                    pieces.append("</a>")
            elif token.tag in tags:
                tag = tags[token.tag]
                pieces.append(f"<{tag}>" if token.nesting == 1 else f"</{tag}>")
        return "".join(pieces)

    story = []
    for node in nodes:
        kind = node["type"]
        if kind == "figure":
            drawing = svg2rlg(io.BytesIO(assets[node["svg"]]))
            scale = width / drawing.width
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            story.extend((drawing, Spacer(1, 6)))
        elif kind == "math":
            drawing = math_drawing(node["text"], True)
            scale = min(1, width / drawing.width)
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            drawing.hAlign = "CENTER"
            story.extend((drawing, Spacer(1, 8)))
        elif kind == "table":
            if not node["rows"]:
                continue
            rows = [
                [
                    Paragraph(
                        inline(cell) if node["token_cells"] else escape(str(cell)).replace("\n", "<br/>"),
                        head_style if i == 0 else cell_style,
                    )
                    for cell in row
                ]
                for i, row in enumerate(node["rows"])
            ]
            table = LongTable(
                rows,
                colWidths=table_widths(node, width),
                repeatRows=1,
                splitByRow=1,
                # In-row splitting is still needed for very long evidence cells.
                # Require at least one text line plus padding in each fragment.
                splitInRow=cell_style.leading + 10,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d9d9")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#36463e")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f5")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.extend((table, Spacer(1, 12)))
        else:
            style = (
                title
                if kind == "title"
                else headings[min(4, node.get("level", 1))]
                if kind == "heading"
                else muted
                if node.get("muted")
                else body
            )
            content = escape(node.get("prefix", "")) + (
                inline(node["tokens"]) if "tokens" in node else escape(node.get("text", "")).replace("\n", "<br/>")
            )
            story.append(Paragraph(content or " ", style))

    def page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont(family, 8)
        canvas.setFillColor(colors.HexColor("#53605a"))
        canvas.drawCentredString(A4[0] / 2, 1.05 * cm, str(doc.page))
        canvas.restoreState()

    pdf = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=1.9 * cm,
        leftMargin=1.9 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=metadata["spec"]["title"],
        author="ThreeMind",
    )
    pdf.build(story, onFirstPage=page_number, onLaterPages=page_number)
