import pytest

from threemind_lab.documents import Documents


def test_multikernel_guide_and_engineering_evidence_are_visible():
    from pathlib import Path

    docs = Documents(Path(__file__).resolve().parents[1])
    assert "lif/1" in docs.read("docs/zh/v2-kernels.md")["markdown"]
    assert "lif/1" in docs.read("docs/en/v2-kernels.md")["markdown"]
    assert docs.read("lab/validations/2026-09-28-kernel-candidates/README.md")
    assert docs.resource("docs/benchmarks/kernel-candidates-2026-09-28.json").stat().st_size < 2 * 1024**2


def test_public_document_resources_cannot_reach_secrets(tmp_path):
    reports = tmp_path / "docs" / "benchmarks"
    reports.mkdir(parents=True)
    report = reports / "result.json"
    report.write_text('{"verified":true}', encoding="utf-8")
    (tmp_path / ".env").write_text("LOCAL_SECRET=not-public", encoding="utf-8")
    (tmp_path / "docs" / "private.json").write_text('{"private":true}', encoding="utf-8")
    docs = Documents(tmp_path)
    assert docs.resource("docs/benchmarks/result.json") == report
    for name in (
        ".env",
        "docs/benchmarks/../../.env",
        "docs/benchmarks/../private.json",
        "data/state.json",
        "docs/benchmarks/missing.json",
        str(tmp_path / ".env"),
    ):
        with pytest.raises(KeyError):
            docs.resource(name)


def test_plans_menu_and_published_english_peer(tmp_path):
    for locale in ("zh", "en"):
        folder = tmp_path / "docs" / locale / "plans"
        folder.mkdir(parents=True)
        (folder / "index.md").write_text(f"# {locale} plans\n", encoding="utf-8")
    (tmp_path / "docs/en/private.md").write_text("# Unlisted", encoding="utf-8")
    docs = Documents(tmp_path)
    assert next(d for d in docs.index()["documents"] if d["id"] == "docs/zh/plans/index.md")["category"] == "plans"
    assert any(c["id"] == "plans" for c in docs.index()["categories"])
    assert docs.read("docs/en/plans/index.md")["markdown"] == "# en plans\n"
    for name in ("docs/en/private.md", "docs/en/plans/../../../../.env"):
        with pytest.raises(KeyError):
            docs.read(name)
