import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from test_readouts import delivery, node

from threemind_core import Config, Engine, Stimulus
from threemind_runtime.activity_readout import ActivityReader
from threemind_runtime.chat_readout import display_readout
from threemind_runtime.readout_config import ActivityReadoutConfig, StructuralReadoutConfig, TemporalReadoutConfig
from threemind_runtime.readout_host import ReadoutHost


def config(**kw):
    return ActivityReadoutConfig(
        **(
            {
                "interval_us": 100000,
                "settle_us": 400000,
                "min_response_us": 600000,
                "max_response_us": 2000000,
                "baseline_us": 0,
            }
            | kw
        )
    )


def observe(values, cfg=None, restore_at=None):
    reader = ActivityReader(cfg or config())
    outputs = []
    for i, ns in enumerate(values):
        outputs += reader.consume(i * 100000, i, ns, [delivery()] if i == 0 else [])
        if i == restore_at:
            reader = ActivityReader(reader.config, json.loads(json.dumps(reader.capture())))
    outputs += reader.close((len(values) - 1) * 100000, "run_ended")
    return outputs


def test_decaying_pattern_is_detected_and_observation_continues_to_response_end():
    values = [[node(1, 0.001 * 0.8**i), node(2, 0.002 * 0.8**i)] for i in range(12)] + [[]] * 9
    (record,) = observe(values)
    assert record["analyses"]["pattern"]["status"] == "converged"
    assert record["analyses"]["pattern"]["amplitude"]["status"] == "decaying"
    assert record["analyses"]["response_end"]["status"] == "ended"
    assert int(record["ranking_time_us"]) < int(record["end_us"])
    assert record["candidate_ids"] == [2, 1]
    assert all(n["last_activation"] == 0 for n in record["nodes"])
    assert display_readout(record)["nodes"][0]["activation"] == pytest.approx(0.002 * 0.8**6)
    assert observe(values, restore_at=8) == [record]


def test_zero_and_subfloor_vectors_never_become_pattern_responses():
    for value in (0, 1e-12):
        (record,) = observe([[node(1, value)]] * 21)
        assert record["primary_result"] is None and record["candidate_ids"] == []
        assert record["classification"] == "response_ended"


def test_same_total_with_rotating_nodes_is_periodic_not_steady_pattern():
    (record,) = observe([[node(1 + i % 2, 0.5)] for i in range(21)])
    assert record["analyses"]["pattern"]["status"] == "not_detected"
    assert record["analyses"]["periodic"]["period_us"] == "200000"
    assert record["analyses"]["amplitude"]["status"] == "stable"


def test_amplitude_periods_with_fixed_membership_are_not_lost():
    (record,) = observe([[node(1, 0.3 if i % 2 else 0.7)] for i in range(21)])
    assert record["analyses"]["periodic"]["period_us"] == "200000"


def test_complete_vectors_prevent_top_one_from_hiding_drift_and_are_budgeted():
    values = [[node(1, 0.7), node(2 + i, 0.3)] for i in range(21)]
    (record,) = observe(values, config(comparison_top_k=1))
    assert record["analyses"]["pattern"]["status"] == "not_detected"
    (bounded,) = observe(values, config(max_series_values=10))
    assert bounded["reason"] == "series_value_budget" and bounded["censored"]
    assert len(bounded["series"]) == 2


def test_old_reader_early_finish_does_not_end_new_reader_or_change_core():
    cfg = Config(propagation_rate=0)
    engine, control = Engine(cfg), Engine(cfg)
    spec = SimpleNamespace(
        structural_readout=StructuralReadoutConfig(enabled=False),
        temporal_readout=TemporalReadoutConfig(
            **{k: v for k, v in asdict(config()).items() if k in TemporalReadoutConfig.__dataclass_fields__}
        ),
        activity_readout=config(),
    )
    records = []
    host = ReadoutHost(spec, "test", 0, record=records.append)
    stim = Stimulus(0, ((1, 0.8),))
    engine.inject(stim)
    control.inject(stim)
    host.delivered(delivery())
    for at in range(0, 2100000, 100000):
        engine.advance_to(at)
        control.advance_to(at)
        host.observe(engine)
    host.close(engine.time_us, "run_ended")
    assert engine.capture_state().digest == control.capture_state().digest
    assert len(records) == 2
    old, new = records
    assert old["payload"]["chat_primary"] is False
    assert new["payload"]["chat_primary"] is True
    assert int(old["payload"]["end_us"]) < int(new["payload"]["end_us"])


def test_activity_api_keeps_comparison_evidence_and_one_primary_chat_message(database):
    from uuid import uuid4

    from test_api import client_for

    from threemind_lab.database import LOCAL_USER
    from threemind_lab.protocols import RunSpec

    engine = Engine(Config(propagation_rate=0, activation_decay_enabled=False, inhibition_gain=0))
    spec = RunSpec(environment="manual", clock="unbounded", config=engine.config.to_dict(), activity_readout=config())
    project = database.create_project({"id": LOCAL_USER}, "Activity analysis acceptance")["id"]
    run = database.create_run(project, "Readout source", spec.model_dump())
    records = []
    host = ReadoutHost(spec, run["id"], 0, record=records.append)
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.4))))
    host.delivered(delivery(id=str(uuid4())))
    for at in range(0, 2100000, 100000):
        engine.advance_to(at)
        host.observe(engine)
    host.close(engine.time_us, "run_ended")
    database.save_checkpoint(
        project,
        run["id"],
        engine.capture_state(),
        expected_revision=0,
        status="completed",
        context={"protocol": spec.model_dump(), "readouts": host.capture()},
        events=records,
    )
    base = f"/api/v2/projects/{project}/runs/{run['id']}"
    with client_for(database) as client:
        history = client.get(base + "/readouts?kind=temporal_readout").json()
        assert len(history["rows"]) == 2
        current = next(r for r in history["rows"] if r["payload"].get("analysis_schema"))
        assert "nodes" not in current["payload"]["analyses"]["pattern"]
        detail = client.get(base + f"/readouts/{current['id']}?order=decision-activation").json()
        assert detail["rows"][0]["item"]["decision_activation"] > 0
        raw = client.get(base + f"/readouts/{current['id']}/export").json()
        assert raw["payload"]["analyses"]["pattern"]["nodes"]
        conversation = client.get(base + "/conversation?passive=false").json()
        assert len(conversation["rows"]) == 1
        assert conversation["rows"][0]["readout"]["analysis_schema"]
