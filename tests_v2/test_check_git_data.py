"""The Git guard checks staged objects and keeps explicit frozen fixtures usable."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/check-git-data.py"
spec = importlib.util.spec_from_file_location("check_git_data", MODULE_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


@pytest.fixture
def guard_repo(tmp_path):
    repo = tmp_path / "index"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Guard Test")
    git(repo, "config", "user.email", "guard-test@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "commit.gpgsign", "false")
    return repo


def test_reviewed_artifacts_are_rejected_even_if_small_or_allowlisted():
    name = "lab/explorations/example/raw-original.json"
    selection = {"groups": [{"paths": [name]}]}
    policy = {"allow_paths": {name: {"max_bytes": 1024**2}}}
    assert "reviewed" in guard.classify_path(name, 1, selection, policy)[0]


@pytest.mark.parametrize("name", [
    "lab/explorations/new/run-04/checkpoint.json.gz",
    "lab/explorations/new/run-04/subject/result.json",
    "lab/explorations/new/trace-02/results.json",
    "lab/explorations/new/inputs.json",
    "lab/explorations/new/host.jsonl.gz",
    "lab/explorations/new/implementation-source.zip",
    "exports/research.tmdata",
    "exports/research.tmdata.001",
    "exports/research.TMDATA.part-02",
])
def test_new_raw_outputs_and_data_bundle_parts_are_rejected(name):
    assert guard.classify_path(name, 20, {}, {})


def test_small_summaries_protocols_and_explicit_fixtures_remain_allowed():
    for name in ("lab/explorations/new/run-04/manifest.json", "lab/explorations/new/run-04/summary-t30.json", "lab/explorations/new/protocol.md", "lab/explorations/new/run.py"):
        assert not guard.classify_path(name, 100, {}, {})
    fixture = "tests_v2/fixtures/frozen.json"
    policy = {"allow_paths": {fixture: {"max_bytes": 2 * 1024**2}}}
    assert not guard.classify_path(fixture, 1024**2, {}, policy)
    assert not guard.classify_path("tests_v2/fixtures/unreviewed.json", 1024**2, {}, policy)
    assert guard.classify_path(fixture, 3 * 1024**2, {}, policy)


@pytest.mark.parametrize("size", [1024**2, 4 * 1024**2, 50 * 1024**2, 100 * 1024**2])
def test_ordinary_manuscripts_follow_github_file_limit(size):
    assert not guard.classify_path("docs/paper/new-revision/manuscript.docx", size, {}, {})


def test_github_file_limit_cannot_be_bypassed_by_an_exception():
    name = "docs/oversized.pdf"
    size = 100 * 1024**2 + 1
    policy = {"allow_paths": {name: {"max_bytes": size}}}
    assert "100 MiB" in guard.classify_path(name, size, {}, policy)[0]


def test_size_check_reads_index_instead_of_changed_worktree(guard_repo, monkeypatch):
    # Exercise the real index with small payloads; exact public limits are tested above.
    monkeypatch.setattr(guard, "MAX_BYTES", 1024**2)
    source = guard_repo / "module.py"
    source.write_bytes(b"#" * (1024**2 + 1))
    git(guard_repo, "add", ".")
    source.write_bytes(b"# small worktree copy\n")
    assert any("file limit" in failure for failure in guard.check_index(guard_repo))
    git(guard_repo, "add", ".")
    source.write_bytes(b"#" * (2 * 1024**2))
    assert not guard.check_index(guard_repo)


def test_policy_is_read_from_index_when_staged(guard_repo):
    source = guard_repo / "frozen.tmind"
    source.write_bytes(b"x" * 1024**2)
    policy_path = guard_repo / guard.POLICY_PATH
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps({"schema": "threemind.git-data-policy/1", "allow_paths": {}}), encoding="utf-8")
    git(guard_repo, "add", ".")
    policy_path.write_text(json.dumps({"schema": "threemind.git-data-policy/1", "allow_paths": {"frozen.tmind": {"max_bytes": 2 * 1024**2}}}), encoding="utf-8")
    assert any("frozen.tmind" in failure for failure in guard.check_index(guard_repo))
    git(guard_repo, "add", guard.POLICY_PATH)
    assert not guard.check_index(guard_repo)


def test_all_index_mode_catches_a_preexisting_original(guard_repo):
    source = guard_repo / "research.tmdata"
    source.write_bytes(b"original")
    git(guard_repo, "add", ".")
    git(guard_repo, "commit", "-qm", "fixture containing preexisting data")
    assert not guard.check_index(guard_repo)
    assert guard.check_index(guard_repo, all_tracked=True)


@pytest.mark.parametrize("size,warning_expected", [(1024, False), (1025, True)])
def test_warning_boundary_and_cli_success(guard_repo, monkeypatch, capsys, size, warning_expected):
    monkeypatch.setattr(guard, "WARN_BYTES", 1024)
    source = guard_repo / "manual.pdf"
    source.write_bytes(b"x" * size)
    git(guard_repo, "add", ".")
    assert guard.main(["--repo", str(guard_repo)]) == 0
    output = capsys.readouterr()
    assert ("WARNING:" in output.err) == warning_expected
    assert "passed" in output.out
    assert not git(guard_repo, "diff", "--name-only")
    assert git(guard_repo, "diff", "--cached", "--name-only") == "manual.pdf"


def install_guard(repo):
    script = repo / "scripts/check-git-data.py"
    script.parent.mkdir()
    script.write_bytes(MODULE_PATH.read_bytes())
    hook = repo / ".githooks/pre-commit"
    hook.parent.mkdir()
    hook.write_bytes((MODULE_PATH.parents[1] / ".githooks/pre-commit").read_bytes())
    hook.chmod(0o755)
    git(repo, "config", "core.hooksPath", ".githooks")


def test_real_hook_accepts_manuscript_over_old_limit(guard_repo):
    install_guard(guard_repo)
    source = guard_repo / "manuscript.docx"
    source.write_bytes(b"publication derivative\n" * 100_000)
    git(guard_repo, "add", ".")
    git(guard_repo, "commit", "-qm", "manuscript above former limit")
    assert git(guard_repo, "log", "-1", "--format=%s") == "manuscript above former limit"


def test_real_hook_rejection_preserves_files_and_index(guard_repo):
    install_guard(guard_repo)
    source = guard_repo / "research.tmdata"
    original = b"original evidence must be preserved"
    source.write_bytes(original)
    git(guard_repo, "add", ".")
    before = git(guard_repo, "ls-files", "--stage")
    result = subprocess.run(["git", "-C", str(guard_repo), "commit", "-qm", "must fail"],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "Commit aborted" in result.stderr
    assert "staged changes are preserved" in result.stderr
    assert source.read_bytes() == original
    assert git(guard_repo, "ls-files", "--stage") == before
    assert subprocess.run(["git", "-C", str(guard_repo), "rev-parse", "--verify", "HEAD"],
                          capture_output=True).returncode != 0
