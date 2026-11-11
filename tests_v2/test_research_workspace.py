import pytest

from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json


def test_workspace_uses_registered_root_and_does_not_reinitialize_old_studies(tmp_path, monkeypatch):
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path / "repo")
    root = tmp_path / "external"
    atomic_json(
        storage.registry_path,
        {
            "schema": "threemind.research-storage/1",
            "resources": {},
            "targets": {},
            "data_root": {"path": str(root), "revision": 1},
        },
    )
    monkeypatch.delenv("THREEMIND_DATA_ROOT", raising=False)
    assert storage.workspace_path("study-new") == root / "experiments/study-new"
    assert not root.exists()
    for name in ("../old", "group/study", "C:/work"):
        with pytest.raises(ValueError):
            storage.workspace_path(name)


def test_maintained_study_accepts_new_managed_root_with_explicit_path(tmp_path, monkeypatch):
    from lab.tools.service_study import ROOT, StudyConfig
    from threemind_lab import config

    monkeypatch.setattr(config, "load_env", lambda: None)
    monkeypatch.setenv("THREEMIND_DATA_ROOT", str(tmp_path / "external"))
    monkeypatch.setenv("THREEMIND_STORAGE_CONTROL", str(tmp_path / "control"))
    storage = ResearchStorage(tmp_path / "control")
    kwargs = {"name": "new", "title": "new", "sources": ROOT / "lab", "usage_start": 0}
    path = storage.workspace_path("new")
    assert StudyConfig(work=path, **kwargs).work == path
    assert StudyConfig(work=ROOT / ".work/historical-fixed", **kwargs).work == ROOT / ".work/historical-fixed"
    with pytest.raises(ValueError, match="dedicated"):
        StudyConfig(work=ROOT.parent / "unmanaged-storage-research-fixture", **kwargs)
    assert not path.exists()
