import copy
import gzip
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lab.tools import study_input_audit
from threemind_lab.inputs import envelope_record
from threemind_runtime.stimulus_units import unit_frames


def fixture(tmp_path, monkeypatch, *, altered_frame=False, pending=False, source_changed=False):
    payload = {
        "units": [
            {
                "kind": "element",
                "time_us": "100",
                "source": "test-sensor",
                "mapping_version": "fixture/1",
                "elements": [{"channel": 17, "value": 0.3}],
                "intensity": 0.2,
                "measurements": [{"physical_raw": -0.0}],
            }
        ]
    }
    original = envelope_record(uuid4(), "stimulus-units", "test", payload, {}, 1, 1)
    stored = copy.deepcopy(original)
    stored["payload"]["units"][0]["measurements"][0]["physical_raw"] = 0.0
    stored.update(run_id="run", status="scheduled" if pending else "completed", filtered_count=0)
    if source_changed:
        stored["source"] = "another-source"
    frame = {
        "run_id": "run",
        "envelope_id": original["id"],
        "frame_index": 0,
        "status": "scheduled" if pending else "delivered",
        "input_gate": None,
        "scheduled_time_us": "100",
        "delivered_time_us": None if pending else "100",
        "stimulus": next(unit_frames(payload))["stimulus"].to_dict(),
    }
    before = copy.deepcopy(frame)
    if altered_frame:
        frame["stimulus"]["intensity"] = 0.8
    folder = tmp_path / "cases" / "fixture"
    folder.mkdir(parents=True)
    with gzip.open(folder / "inputs.json.gz", "wb") as stream:
        stream.write(
            json.dumps(
                {"envelopes": [original], "frames": [before], "delivered": [] if pending else [before], "rejected": []}
            ).encode()
        )

    def export(db, project, run, *, records, format):
        yield json.dumps({"run_id": run, "records": records}) + "\n"
        yield json.dumps(stored if records == "envelopes" else frame) + "\n"

    monkeypatch.setattr(study_input_audit, "export_stream", export)
    return SimpleNamespace(work=tmp_path, db=None, project="project"), folder, {"id": "run", "seed": 1}


def test_jsonb_negative_zero_is_reported_without_rewriting_original_or_stimulus(tmp_path, monkeypatch):
    study, folder, row = fixture(tmp_path, monkeypatch)
    before = (folder / "inputs.json.gz").read_bytes()
    result = study_input_audit.verify_input_bundle(study, folder, row)
    assert len(result["metadata_normalizations"]) == 1
    assert result["frames"] == result["envelopes"] == 1 and result["pending_frames"] == 0
    assert (folder / "inputs.json.gz").read_bytes() == before


def test_changed_actual_stimulus_cannot_be_excused_as_metadata_normalization(tmp_path, monkeypatch):
    study, folder, row = fixture(tmp_path, monkeypatch, altered_frame=True)
    with pytest.raises(AssertionError):
        study_input_audit.verify_input_bundle(study, folder, row)


def test_pending_input_is_only_accepted_in_explicit_partial_audit(tmp_path, monkeypatch):
    study, folder, row = fixture(tmp_path, monkeypatch, pending=True)
    with pytest.raises(AssertionError):
        study_input_audit.verify_input_bundle(study, folder, row)
    result = study_input_audit.verify_input_bundle(study, folder, row, require_complete=False)
    assert result["pending_frames"] == 1


def test_metadata_value_equivalence_is_type_aware():
    same = study_input_audit.jsonb_value_equal
    assert same({"measurement": [-0.0, 1.0]}, {"measurement": [0.0, 1]})
    assert not same({"measurement": [0.0]}, {"measurement": [False]})
    assert not same({"measurement": [1.0]}, {"measurement": ["1.0"]})
    assert not same({"measurement": [1.0]}, {"measurement": [1.1]})


def test_changed_source_is_rejected_even_when_decoded_stimulus_matches(tmp_path, monkeypatch):
    study, folder, row = fixture(tmp_path, monkeypatch, source_changed=True)
    with pytest.raises(AssertionError):
        study_input_audit.verify_input_bundle(study, folder, row)
