"""Personal authoring documents; never executable code or scientific measurements."""

import json
import re
from html.parser import HTMLParser
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from markdown_it import MarkdownIt
from pydantic import Field, field_validator

from .protocols import StrictModel

MAX_BODY_BYTES = 1024 * 1024
BLOCKS = {
    "paragraph",
    "heading",
    "bulletList",
    "orderedList",
    "taskList",
    "blockquote",
    "codeBlock",
    "horizontalRule",
    "image",
    "blockMath",
    "table",
}
INLINE = {"text", "hardBreak", "inlineMath"}
ATTRS = {
    "doc": set(),
    "text": set(),
    "hardBreak": set(),
    "horizontalRule": set(),
    "paragraph": {"textAlign"},
    "heading": {"textAlign", "level"},
    "bulletList": set(),
    "orderedList": {"start", "type"},
    "listItem": set(),
    "taskList": set(),
    "taskItem": {"checked"},
    "blockquote": set(),
    "table": set(),
    "tableRow": set(),
    "tableCell": {"colspan", "rowspan", "colwidth", "align"},
    "tableHeader": {"colspan", "rowspan", "colwidth", "align"},
    "codeBlock": {"language"},
    "image": {"src", "alt", "title", "width", "height"},
    "inlineMath": {"latex"},
    "blockMath": {"latex"},
}
MARKS = {
    "bold": set(),
    "italic": set(),
    "strike": set(),
    "code": set(),
    "underline": set(),
    "link": {"href", "title", "target", "rel", "class"},
    "highlight": {"color"},
    "textStyle": {"color", "backgroundColor", "fontSize", "fontFamily", "lineHeight"},
}


def bounded_text(value, maximum=MAX_BODY_BYTES):
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("document text must be a string without NUL characters")
    try:
        if len(value.encode("utf-8")) > maximum:
            raise ValueError("document text exceeds its byte budget")
    except UnicodeError as error:
        raise ValueError("document text must be valid Unicode") from error
    return value


def safe_url(value):
    bounded_text(value, 4096)
    if any(ord(char) < 32 for char in value) or "\\" in value:
        raise ValueError("invalid document URL")
    parsed = urlsplit(value)
    if parsed.scheme.lower() in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
        return value
    if parsed.scheme.lower() == "mailto" or value.startswith("#"):
        return value
    if value.startswith("/") and not value.startswith("//") and not parsed.netloc:
        return value
    raise ValueError("use an HTTP(S), mailto, fragment or local document URL")


def validate_attrs(kind, attrs, allowed):
    if not isinstance(attrs, dict) or set(attrs) - allowed:
        raise ValueError(f"unsupported attributes for document {kind}")
    for key, value in attrs.items():
        if value is None:
            continue
        if key in ("href", "src"):
            safe_url(value)
            if key == "src" and urlsplit(value).scheme == "mailto":
                raise ValueError("an image requires an HTTP(S) or local URL")
        elif key in ("color", "backgroundColor"):
            if not isinstance(value, str) or len(value) > 100:
                raise ValueError("invalid document color")
            if value and not re.fullmatch(r"#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,24}|rgba?\([\d.,%\s]+\)", value):
                raise ValueError("invalid document color")
        elif key in ("fontSize", "lineHeight"):
            if (
                not isinstance(value, str)
                or value
                and not re.fullmatch(r"\d{1,3}(?:\.\d{1,3})?(?:px|pt|em|rem|%)?", value)
            ):
                raise ValueError("unsupported document font size or line height")
        elif key == "fontFamily":
            if not isinstance(value, str) or value and not re.fullmatch(r'[\w\s,\-"\']{1,160}', value):
                raise ValueError("unsupported document font family")
        elif key in ("textAlign", "align"):
            if value not in ("", "left", "right", "center", "justify", "start", "end"):
                raise ValueError("invalid document alignment")
        elif key in ("level", "start", "colspan", "rowspan"):
            if type(value) is not int or not 1 <= value <= (6 if key == "level" else 100000 if key == "start" else 100):
                raise ValueError("invalid document structural number")
        elif key == "colwidth":
            if (
                not isinstance(value, list)
                or not 1 <= len(value) <= 100
                or any(type(v) is not int or not 1 <= v <= 10000 for v in value)
            ):
                raise ValueError("invalid table column widths")
            if len(value) != attrs.get("colspan", 1):
                raise ValueError("table column widths must match colspan")
        elif key == "checked":
            if type(value) is not bool:
                raise ValueError("task checked state must be boolean")
        elif key in ("width", "height"):
            if isinstance(value, bool) or not re.fullmatch(r"\d{1,4}", str(value)) or not 1 <= int(value) <= 10000:
                raise ValueError("invalid image dimensions")
        else:
            bounded_text(value, 8192 if key == "latex" else 1024)


def validate_document(document):
    if not isinstance(document, dict) or document.get("type") != "doc":
        raise ValueError("a document root is required")
    try:
        bounded_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
    except (RecursionError, TypeError) as error:
        raise ValueError("invalid or excessively nested document") from error
    total = 0

    def visit(node, depth=0):
        nonlocal total
        total += 1
        if total > 20000 or depth > 32:
            raise ValueError("document exceeds node or nesting budget")
        if not isinstance(node, dict) or set(node) - {"type", "attrs", "content", "text", "marks"}:
            raise ValueError("invalid document node")
        kind = node.get("type")
        if not isinstance(kind, str) or kind not in ATTRS or kind == "doc" and depth:
            raise ValueError("unsupported document node type")
        validate_attrs(kind, node.get("attrs", {}), ATTRS[kind])
        if kind == "text":
            bounded_text(node.get("text"))
            if not node["text"] or node.get("content"):
                raise ValueError("text nodes require nonempty text and no children")
        elif "text" in node:
            raise ValueError("only text nodes carry text")
        marks = node.get("marks", [])
        if not isinstance(marks, list) or len(marks) > 10:
            raise ValueError("invalid document marks")
        seen = set()
        for mark in marks:
            if (
                not isinstance(mark, dict)
                or set(mark) - {"type", "attrs"}
                or not isinstance(mark.get("type"), str)
                or mark.get("type") not in MARKS
                or mark["type"] in seen
            ):
                raise ValueError("unsupported or duplicate document mark")
            seen.add(mark["type"])
            validate_attrs(mark["type"], mark.get("attrs", {}), MARKS[mark["type"]])
        if marks and kind not in INLINE:
            raise ValueError("only inline content can have marks")
        children = node.get("content", [])
        if not isinstance(children, list):
            raise ValueError("document children must be a list")  # noqa: TRY004 - handled as a 422 validation error
        allowed = (
            INLINE
            if kind in ("paragraph", "heading")
            else {"text"}
            if kind == "codeBlock"
            else {"listItem"}
            if kind in ("bulletList", "orderedList")
            else {"taskItem"}
            if kind == "taskList"
            else {"tableRow"}
            if kind == "table"
            else {"tableCell", "tableHeader"}
            if kind == "tableRow"
            else BLOCKS
            if kind in ("doc", "blockquote", "listItem", "taskItem", "tableCell", "tableHeader")
            else set()
        )
        if any(
            not isinstance(c, dict) or not isinstance(c.get("type"), str) or c["type"] not in allowed for c in children
        ):
            raise ValueError("invalid document child placement")
        if kind in ("listItem", "taskItem") and (not children or children[0]["type"] != "paragraph"):
            raise ValueError("list items must start with a paragraph")
        if (
            kind
            in ("table", "tableRow", "tableCell", "tableHeader", "blockquote", "bulletList", "orderedList", "taskList")
            and not children
        ):
            raise ValueError("document container cannot be empty")
        for child in children:
            visit(child, depth + 1)
        if kind == "table":
            # Do not let an editor silently repair a saved, inconsistent table.
            occupied = set()
            row_widths = {}
            width = None
            for y, row in enumerate(children):
                x = 0
                for cell in row["content"]:
                    while (x, y) in occupied:
                        x += 1
                    attrs = cell.get("attrs", {})
                    cols, rows = attrs.get("colspan") or 1, attrs.get("rowspan") or 1
                    if x + cols > 1000 or y + rows > len(children):
                        raise ValueError("table spans exceed the table bounds")
                    if len(occupied) + cols * rows > 20000:
                        raise ValueError("table exceeds its layout cell budget")
                    for cy in range(y, y + rows):
                        for cx in range(x, x + cols):
                            if (cx, cy) in occupied:
                                raise ValueError("table cells overlap")
                            occupied.add((cx, cy))
                            row_widths[cy] = max(row_widths.get(cy, 0), cx + 1)
                    x += cols
                row_width = row_widths.get(y, 0)
                width = row_width if width is None else width
                if row_width != width or any((cx, y) not in occupied for cx in range(width)):
                    raise ValueError("table rows must cover the same number of columns")

    visit(document)
    return document


class MarkdownBody(StrictModel):
    format: Literal["markdown"]
    text: str = Field(max_length=MAX_BODY_BYTES, strict=True)

    @field_validator("text")
    @classmethod
    def check_text(cls, value):
        return bounded_text(value)


class RichBody(StrictModel):
    format: Literal["document"]
    content: dict

    @field_validator("content")
    @classmethod
    def check_document(cls, value):
        return validate_document(value)


Body = Annotated[MarkdownBody | RichBody, Field(discriminator="format")]


class NoteEdit(StrictModel):
    operation_id: UUID
    expected_revision: int = Field(strict=True, ge=0)
    title: str = Field(min_length=1, max_length=200, strict=True)
    kind: Literal["draft", "note"] = "draft"
    collection_id: UUID | None = None
    body: Body

    @field_validator("title")
    @classmethod
    def check_title(cls, value):
        if not value.strip():
            raise ValueError("a note title is required")
        return bounded_text(value, 800)


class CollectionEdit(StrictModel):
    name: str = Field(min_length=1, max_length=100, strict=True)
    color: str = Field(default="#237969", pattern=r"^#[0-9a-fA-F]{6}$")
    kind: Literal["notebook", "category"] = "notebook"
    expected_revision: int = Field(default=0, ge=0, strict=True)

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        if not value.strip():
            raise ValueError("a collection name is required")
        return bounded_text(value, 400)


def body_links(body):
    """Only real markup references are protected; paths inside code stay literal."""
    urls = set()

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if (tag == "img" and key == "src" or tag == "a" and key == "href") and value:
                    urls.add(safe_url(value))

    if body["format"] == "document":

        def visit(node):
            if node["type"] == "image" and node.get("attrs", {}).get("src"):
                urls.add(safe_url(node["attrs"]["src"]))
            for mark in node.get("marks", []):
                if mark["type"] == "link" and mark.get("attrs", {}).get("href"):
                    urls.add(safe_url(mark["attrs"]["href"]))
            for child in node.get("content", []):
                visit(child)

        visit(body["content"])
    else:
        parser = Links()

        def tokens(items):
            for token in items:
                if token.type == "image":
                    urls.add(safe_url(token.attrGet("src")))
                elif token.type == "link_open":
                    urls.add(safe_url(token.attrGet("href")))
                elif token.type in ("html_block", "html_inline"):
                    parser.feed(token.content)
                if token.children:
                    tokens(token.children)

        tokens(MarkdownIt("commonmark", {"maxNesting": 32}).enable(["table", "strikethrough"]).parse(body["text"]))
    return urls


def search_text(body):
    if body["format"] == "markdown":
        return body["text"]
    parts = []

    def visit(node):
        if node.get("text"):
            parts.append(node["text"])
        attrs = node.get("attrs", {})
        parts.extend(str(attrs[key]) for key in ("latex", "alt", "title") if attrs.get(key))
        for child in node.get("content", []):
            visit(child)

    visit(body["content"])
    return "\n".join(parts)
