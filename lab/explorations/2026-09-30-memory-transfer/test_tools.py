import copy
import math

import materials
import pytest
from materials import channel_dose, config, cue_unit, dose, frame, identities, physical_clip, transform

from threemind_core import Stimulus
from threemind_runtime import create_engine
from threemind_runtime.world import PhysicalWorld


def test_controls_preserve_recording_and_declared_dose(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "WORK", tmp_path)
    units = physical_clip(930199, 1)["units"]
    original = copy.deepcopy(units)
    removed = transform(units, "no_imu", 930199)
    matched = transform(units, "dose_matched", 930199)
    shuffled = transform(units, "shuffled_imu", 930199)
    assert units == original
    assert dose(matched) == pytest.approx(dose(removed), abs=1e-12)
    assert dose(units) > dose(removed) > 0
    assert channel_dose(shuffled) == pytest.approx(channel_dose(units), abs=1e-12)
    assert [u["time_us"] for u in shuffled] == [u["time_us"] for u in units]
    for u in (*removed, *matched, *shuffled):
        assert frame(u).intensity == 1.0


def test_cue_and_sensory_identities_do_not_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "WORK", tmp_path)
    ids = identities(930199)
    channels = set()
    for sign in (1, -1):
        channels.update(channel_dose(physical_clip(930199, sign)["units"]))
    assert channels.isdisjoint(ids[k] for k in ("A", "B", "C", "X", "Y", "keep"))
    assert {ids["position_positive"], ids["position_negative"]} <= channels
    assert frame(cue_unit(10, ids["A"], 0.45)) == Stimulus(10, ((ids["A"], 1.0),), 0.45)


def test_readonly_inspection_recovery_and_physics_are_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "WORK", tmp_path)
    record = physical_clip(930199, 1)
    a = create_engine(config("facilitation"), kernel_id=materials.KERNEL, backend="native")
    b = create_engine(config("facilitation"), kernel_id=materials.KERNEL, backend="native")
    for unit in record["units"]:
        s = frame(unit)
        a.inject(s)
        b.inject(s)
        a.advance_to(s.time_us)
        a.metrics()
        a.observation_nodes()
        before = a.capture_state()
        restored = create_engine(state=before, backend="native")
        b.advance_to(s.time_us)
        assert restored.capture_state().digest == a.capture_state().digest == b.capture_state().digest
    with PhysicalWorld(record["spec"], 930199, record["initial"]) as world:
        for unit in record["units"]:
            assert world.sample(int(unit["time_us"]) - materials.PERIOD) == frame(unit)
        assert world.capture() == record["final"]


def test_order_materials_have_equal_marginals_and_distinct_order(tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "WORK", tmp_path)
    a, b = (physical_clip(930199, sign)["units"] for sign in (1, -1))
    ab, ba = a + b, b + a
    assert channel_dose(ab) == pytest.approx(channel_dose(ba), abs=1e-12)
    assert ab != ba
    assert all(math.isfinite(x) for x in channel_dose(ab).values())


def test_edge_intervention_restores_state_except_audit_counter():
    from verify_memory import select

    engine = create_engine(config("ordinary"), kernel_id=materials.KERNEL, backend="native")
    # Two separated triplets provide target and equal-count control edges.
    for time_us, channels in ((0, (1, 2, 3)), (200000, (4, 5, 6))):
        engine.inject(Stimulus(time_us, tuple((ch, 1.0) for ch in channels), 0.3))
        engine.advance_to(time_us + 100000)
    before = engine.capture_state().to_dict()
    chosen, matched, errors = select(before, 1, (2, 5))
    assert len(chosen) == len(matched) == len(errors)
    forbidden = {n["id"] for n in before["nodes"] if n["channel"] in (1, 2, 5)}
    assert all(not set(k) & forbidden for k in matched)
    engine.intervene(edges=chosen, action="silence")
    engine.intervene(edges=chosen, action="unsilence")
    after = engine.capture_state().to_dict()
    assert after.pop("sequence") == before.pop("sequence") + 2
    assert before == after


def test_budget_admission_remains_immediate_between_storage_scans(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    import common

    monkeypatch.setattr(common, "WORK", tmp_path)
    monkeypatch.setattr(common.psutil, "Process", lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=10)))
    monkeypatch.setattr(common.psutil, "virtual_memory", lambda: SimpleNamespace(available=100 * common.GIB))
    monkeypatch.setattr(common.shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * common.GIB))
    study = common.Study.__new__(common.Study)
    study.meta = {"started_at_epoch": time.time(), "usage_stop_percent": 76}
    study.last_check = 0
    study.last_storage_check = time.time()
    study.active_case = None
    study.completed_count = 1536
    study.completed_wall = 0
    with pytest.raises(RuntimeError, match="instance budget"):
        study.guard(force=True)
    study.completed_count = 1535
    study.completed_wall = 14401
    with pytest.raises(RuntimeError, match="simulation budget"):
        study.guard(force=True)
    study.completed_wall = 0
    # No database attribute: a repeated admission must not rescan storage.
    study.guard(force=True)


def test_export_signed_zero_recovery_requires_original_evidence_and_hash():
    from export_inputs import add_measurements, digest, normalize_zero, recover_payload, zero_sign_differences

    measurements = [{"kind": "accelerometer", "values": [1.0, -0.0, 0.0]}]
    original = {"units": [{"elements": [{"channel": 1, "value": 0.3}], "measurements": measurements}]}
    row = {"id": "evidence-test", "payload": normalize_zero(original), "payload_hash": digest(original)}
    with pytest.raises(AssertionError, match="unavailable"):
        recover_payload(row, {})
    index = {}
    add_measurements(index, measurements, "original-physics-recording")
    recovered = recover_payload(row, index)
    assert recovered["zero_sign_paths"] == ["/units/0/measurements/0/values/1"]
    assert digest(recovered["original_payload"]) == row["payload_hash"]
    assert recovered["core_input_unchanged"]
    corrupted = copy.deepcopy(row)
    corrupted["payload"]["units"][0]["elements"][0]["value"] = 0.4
    with pytest.raises(AssertionError, match="not recoverable"):
        recover_payload(corrupted, index)
    with pytest.raises(AssertionError, match="value changed"):
        zero_sign_differences([0.0], [0.1])
