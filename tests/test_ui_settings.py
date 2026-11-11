from __future__ import annotations

import json

import threemind.api as api


def test_checked_in_example_matches_complete_runtime_defaults() -> None:
    example = api._project_root / "data" / "ui-settings.example.json"

    assert json.loads(example.read_text(encoding="utf-8")) == api._default_ui_settings_document()


def test_missing_ui_settings_are_created_with_complete_defaults(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ui-settings.json"
    monkeypatch.setattr(api, "SETTINGS_PATH", settings_path)

    loaded = api._load_ui_settings()

    assert loaded == api._default_ui_settings_document()
    assert json.loads(settings_path.read_text(encoding="utf-8")) == loaded
    assert len(loaded["adapter_preferences"]) == len(api.default_adapter_registry().ids())


def test_existing_ui_settings_are_merged_in_memory_without_rewrite(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ui-settings.json"
    original = '{\n  "ui": {"locale": "en"},\n  "observer": {"min_nodes": 9},\n  "custom": {"preserved": true}\n}\n'
    settings_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(api, "SETTINGS_PATH", settings_path)

    loaded = api._load_ui_settings()

    assert settings_path.read_text(encoding="utf-8") == original
    assert loaded["ui"]["locale"] == "en"
    assert loaded["observer"]["min_nodes"] == 9
    assert loaded["observer"]["max_nodes"] == api.DEFAULT_UI_SETTINGS["observer"]["max_nodes"]
    assert loaded["custom"] == {"preserved": True}


def test_existing_invalid_ui_settings_are_not_overwritten(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ui-settings.json"
    original = "{not valid json\n"
    settings_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(api, "SETTINGS_PATH", settings_path)

    loaded = api._load_ui_settings()

    assert settings_path.read_text(encoding="utf-8") == original
    assert loaded == api.DEFAULT_UI_SETTINGS


def test_first_run_creator_refuses_to_replace_existing_file(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ui-settings.json"
    settings_path.write_text('{"owner": "user"}\n', encoding="utf-8")
    monkeypatch.setattr(api, "SETTINGS_PATH", settings_path)

    assert api._create_ui_settings_if_missing(api._default_ui_settings_document()) is False
    assert settings_path.read_text(encoding="utf-8") == '{"owner": "user"}\n'
