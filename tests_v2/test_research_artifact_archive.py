"""Offline evidence relocation must preserve bytes and reject ambiguous changes."""

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/research_artifact_archive.py"
spec = importlib.util.spec_from_file_location("research_artifact_archive", MODULE_PATH)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


@pytest.fixture
def fixture_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Archive Test")
    git(repo, "config", "user.email", "archive-test@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    root = repo / "lab/explorations/fixture"
    root.mkdir(parents=True)
    (root / "results.json").write_bytes(b'{"source_commit":"scientific-original","rows":[1]}\n')
    (root / "old-record.json").write_bytes(b'{"failed":true,"input":[0]}\n')
    (root / "run.py").write_bytes(b"# frozen runner\n")
    (root / "report.zh.md").write_bytes(b"# original report\n")
    (root / "summary.json").write_bytes(b'{"total":1}\n')
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "original evidence")
    (root / "results.json").write_bytes(b'{"source_commit":"scientific-original","rows":[1,2]}\n')
    (root / "old-record.json").unlink()
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "append and preserve history")
    raw_path = "lab/explorations/fixture/results.json"
    selection = {
        "schema": archive.SELECTION_SCHEMA,
        "batch": "fixture",
        "base_commit": git(repo, "rev-parse", "HEAD"),
        "status": "approved-for-copy-no-source-delete",
        "destination_root": "data/experiments",
        "path_mapping": [{"prefix": "lab/explorations/", "replace_with": ""}],
        "groups": [{
            "id": "raw",
            "prefix": "lab/explorations/fixture/",
            "patterns": ["results.json", "old-record.json"],
            "paths": [],
            "expected_current": {
                "files": 1,
                "bytes": (root / "results.json").stat().st_size,
                "paths_sha256": hashlib.sha256((raw_path + "\n").encode()).hexdigest(),
            },
        }],
    }
    return repo, selection


def test_archive_keeps_current_and_historical_bytes_and_is_idempotent(fixture_repo):
    repo, selection = fixture_repo
    before_head = git(repo, "rev-parse", "HEAD")
    original = (repo / "lab/explorations/fixture/results.json").read_bytes()
    inventory = archive.build_inventory(repo, selection)
    assert len(inventory["entries"]) == 2  # Includes the deleted historical record.
    assert len(inventory["companions"]) == 3
    first = archive.archive_inventory(repo, inventory)
    second = archive.archive_inventory(repo, inventory)
    assert first["copied"] == 6 and first["reused"] == 0
    assert second["copied"] == 0 and second["reused"] == 6
    assert (repo / "lab/explorations/fixture/results.json").read_bytes() == original
    assert git(repo, "rev-parse", "HEAD") == before_head
    assert "scientific-original" in archive.resolve_archived_path(repo, inventory, "lab/explorations/fixture/results.json").read_text()
    for entry in inventory["entries"]:
        for record in entry["versions"]:
            path = repo / "data/experiments" / record["archive_key"]
            assert path.read_bytes() == subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", record["git_blob"]])
    locations = archive.build_relocations(repo, inventory)
    assert locations["snapshot_commit"] == before_head
    assert all(entry["state"] == "verified" for entry in locations["entries"])
    assert locations["entries"][0]["historical_only"] is True
    receipt = repo / "data/storage-control/research-artifact-archive/fixture/receipt.json"
    assert json.loads(receipt.read_bytes())["source_deleted"] is False


def test_inventory_and_location_index_are_integrity_checked(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    path = archive.publish_inventory(repo, "data/storage-control/fixture/inventory.json", inventory)
    assert archive.load_inventory(path) == inventory
    archive.archive_inventory(repo, inventory)
    output = archive.publish_relocations(repo, "lab/artifact-index/fixture.json", inventory)
    assert json.loads(output.read_bytes()) == archive.build_relocations(repo, inventory)
    raw = json.loads(path.read_bytes())
    raw["base_commit"] = "0" * 40
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(archive.ArchiveError, match="integrity"):
        archive.load_inventory(path)


def test_changed_original_and_existing_different_destination_are_rejected(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    source = repo / "lab/explorations/fixture/results.json"
    original = source.read_bytes()
    source.write_bytes(b"changed during planning")
    with pytest.raises(archive.ArchiveError, match="differs"):
        archive.archive_inventory(repo, inventory)
    source.write_bytes(original)
    destination = repo / "data/experiments/fixture/results.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"other evidence")
    with pytest.raises(archive.ArchiveError, match="different bytes"):
        archive.archive_inventory(repo, inventory)
    assert destination.read_bytes() == b"other evidence"
    assert source.read_bytes() == original


def test_corrupt_archive_cannot_publish_verified_location(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    archive.archive_inventory(repo, inventory)
    (repo / "data/experiments/fixture/results.json").write_bytes(b"corrupt")
    with pytest.raises(archive.ArchiveError, match="corrupt"):
        archive.publish_relocations(repo, "lab/artifact-index/fixture.json", inventory)
    assert not (repo / "lab/artifact-index/fixture.json").exists()


def test_head_and_scope_drift_are_rejected(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    bad_selection = json.loads(json.dumps(selection))
    bad_selection["groups"][0]["expected_current"]["files"] += 1
    with pytest.raises(archive.ArchiveError, match="scope changed"):
        archive.build_inventory(repo, bad_selection)
    git(repo, "commit", "--allow-empty", "-qm", "another actor changed history")
    with pytest.raises(archive.ArchiveError, match="HEAD changed"):
        archive.build_inventory(repo, selection)
    with pytest.raises(archive.ArchiveError, match="HEAD/refs changed"):
        archive.archive_inventory(repo, inventory)


@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", "x/../outside", "x\\outside", "x//outside", ".git/objects", "x\nother"])
def test_path_escape_is_rejected(tmp_path, path):
    with pytest.raises(archive.ArchiveError):
        archive.safe_path(tmp_path, path)


def test_symlink_root_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        (repo / "data").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit temporary symlinks")
    with pytest.raises(archive.ArchiveError, match="Symlink/junction"):
        archive.safe_path(repo, "data/experiments/record.json")


def test_archive_remains_verifiable_after_source_removal(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    archive.archive_inventory(repo, inventory)
    (repo / "lab/explorations/fixture/results.json").unlink()
    assert archive.verify_inventory(repo, inventory)["files"] == 6
    with pytest.raises(archive.ArchiveError, match="Source missing"):
        archive.verify_inventory(repo, inventory, sources=True)


def test_git_text_filters_do_not_replace_original_worktree_bytes(fixture_repo):
    repo, selection = fixture_repo
    git(repo, "config", "core.autocrlf", "true")
    source = repo / "lab/explorations/fixture/results.json"
    source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
    selection["groups"][0]["expected_current"]["bytes"] = source.stat().st_size
    inventory = archive.build_inventory(repo, selection)
    entry = next(item for item in inventory["entries"] if item["source_path"].endswith("results.json"))
    git_record = next(item for item in entry["versions"] if item["git_blob"] == entry["current_blob"])
    assert entry["current"]["sha256"] != git_record["sha256"]
    archive.archive_inventory(repo, inventory)
    assert archive.resolve_archived_path(repo, inventory, entry["source_path"]).read_bytes() == source.read_bytes()
    exact_git = archive.resolve_archived_path(repo, inventory, entry["source_path"], git_blob=entry["current_blob"])
    assert exact_git.read_bytes() == subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", entry["current_blob"]])


def test_location_revision_requires_prior_hash_and_preserves_prior_bytes(fixture_repo):
    repo, selection = fixture_repo
    inventory = archive.build_inventory(repo, selection)
    archive.archive_inventory(repo, inventory)
    relative = "lab/artifact-index/current.json"
    prior = archive.safe_path(repo, relative)
    prior.parent.mkdir(parents=True)
    original = b'{"previous_revision":true}\n'
    prior.write_bytes(original)
    with pytest.raises(archive.ArchiveError, match="expected prior hash"):
        archive.publish_relocations(repo, relative, inventory)
    expected_hash = hashlib.sha256(original).hexdigest()
    archive.publish_relocations(repo, relative, inventory, replace_expected_sha256=expected_hash)
    assert json.loads(prior.read_bytes()) == archive.build_relocations(repo, inventory)
    saved = repo / f"data/storage-control/research-artifact-archive/fixture/prior-relocations/{expected_hash}.json"
    assert saved.read_bytes() == original
