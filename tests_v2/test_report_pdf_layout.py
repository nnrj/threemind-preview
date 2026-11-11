import copy
import io

import pytest
from pypdf import PdfReader

from threemind_lab.report_layout import pdf_document


@pytest.mark.parametrize("lines", [44, 45, 46])
def test_pdf_table_does_not_leave_an_empty_fragment_below_its_header(lines):
    nodes = [
        {"type": "paragraph", "text": "\n".join(["引言"] * lines)},
        {
            "type": "table",
            "token_cells": False,
            "rows": [["FIELD", "OBSERVATION"], ["FIRST-ROW", "\n".join(["complete population observation"] * 6)]],
        },
    ]
    output = io.BytesIO()
    pdf_document(nodes, {}, output, {"spec": {"title": "Table pagination"}}, {})
    pages = [page.extract_text() for page in PdfReader(output).pages]
    assert len(pages) == 2
    assert all("FIRST-ROW" in text or "complete population observation" in text for text in pages if "FIELD" in text)
    assert "FIRST-ROW" in "\n".join(pages)


def test_pdf_oversized_cell_preserves_all_text_across_pages():
    text = "\n".join(f"observation-{i:03d}" for i in range(180))
    output = io.BytesIO()
    pdf_document(
        [{"type": "table", "token_cells": False, "rows": [["FIELD", "OBSERVATION"], ["INDIVIDUAL", text]]}],
        {},
        output,
        {"spec": {"title": "Oversized evidence"}},
        {},
    )
    pages = [page.extract_text() for page in PdfReader(output).pages]
    assert len(pages) >= 3
    combined = "\n".join(pages)
    for i in range(180):
        assert f"observation-{i:03d}" in combined


def test_exported_histogram_distinguishes_nearby_bins_and_declares_the_offset():
    from threemind_lab.report_publication import chart_assets

    block = {
        "chart": "histogram",
        "metric": "body_reserve",
        "data": {
            "method": "complete-distribution/1",
            "unit": "body resource units",
            "rows": [
                {"lower": 9.99998, "upper": 9.999985, "count": 1},
                {"lower": 9.999985, "upper": 9.99999, "count": 2},
            ],
        },
    }
    original = copy.deepcopy(block)
    assets = chart_assets(block, "en")
    svg = assets["svg"].decode()
    assert "Bin boundaries are offsets from 9.99998" in svg
    assert "5e-06" in svg and "1e-05" in svg and "10 to 10" not in svg
    assert assets["png"].startswith(b"\x89PNG")
    assert block == original
