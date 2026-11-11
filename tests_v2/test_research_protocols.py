import pytest

from threemind_core import Config, Engine, Stimulus
from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import Phase, RunSpec, StudySpec, filter_stimulus
from threemind_lab.statistics import phase_evidence, summarize
from threemind_lab.worker import Worker
from threemind_runtime import create_engine
from threemind_runtime.adapters import PlanarBody


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_physical_readout_matches_graph_without_changing_state(backend):
    engine = create_engine(Config(), backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.3))))
    engine.advance_to(12345)
    original = engine.capture_state().digest
    a, b = PlanarBody(91), PlanarBody(91)
    for _ in range(3):
        assert a.sample(engine.time_us, engine.graph()) == b.sample(engine.time_us, engine.activations())
        assert a.capture() == b.capture()
    assert engine.capture_state().digest == original
    assert engine.activations() == [(r["id"], r["activation"]) for r in engine.graph()["nodes"]]
    ref = Engine(state=engine.capture_state()).metrics()
    for metric in ("mean_activation", "active_fraction", "saturated_fraction", "edge_density"):
        assert engine.metrics()[metric] == pytest.approx(ref[metric])


def test_protocol_gates_delivery_and_rejects_inconsistent_design():
    spec = RunSpec(
        duration_s=0.3,
        phases=[
            Phase(name="drive", duration_s=0.1),
            Phase(name="quiet", duration_s=0.1, input_enabled=False),
            Phase(name="recovery", duration_s=0.1),
        ],
        max_channels=1,
    )
    for time_us, enabled in ((99999, True), (100000, False), (199999, False), (200000, True), (300000, False)):
        item = filter_stimulus(spec, Stimulus(40000 + time_us, ((1, 0.2), (2, 0.8))), 40000)
        assert (item is not None) == enabled
        if item is not None:
            assert item.channels == ((2, 0.8),)
    with pytest.raises(ValueError, match="sum"):
        RunSpec(duration_s=1, phases=spec.phases)
    with pytest.raises(ValueError, match="reopened"):
        RunSpec(
            duration_s=0.3,
            phases=[*spec.phases[:1], spec.phases[1].model_copy(update={"close_sources": True}), spec.phases[2]],
        )
    with pytest.raises(ValueError, match="must match"):
        StudySpec(
            name="Phase validation",
            base=spec,
            arms=[{"name": "a"}, {"name": "b", "phases": [Phase(name="other", duration_s=0.3)]}],
        )


def test_phase_resume_matches_uninterrupted_physics_and_recording(database, monkeypatch):
    project = database.create_project({"id": LOCAL_USER}, "Withdrawal resume")
    spec = RunSpec(
        clock="unbounded",
        duration_s=0.22,
        sample_us=10000,
        checkpoint_us=30000,
        phases=[
            Phase(name="drive", duration_s=0.053),
            Phase(name="quiet", duration_s=0.071, input_enabled=False),
            Phase(name="recovery", duration_s=0.096),
        ],
        max_channels=2,
    )
    a, b = [database.create_run(project["id"], name, spec.model_dump()) for name in ("continuous", "interrupted")]
    worker = Worker(database)
    database.enqueue(project["id"], "run", run_id=a["id"])
    assert worker.once()
    assert database.get_run(project["id"], a["id"])["status"] == "completed"
    save = database.save_checkpoint

    def stop_after_commit(*args, **kwargs):
        result = save(*args, **kwargs)
        worker.stopping = True
        return result

    monkeypatch.setattr(database, "save_checkpoint", stop_after_commit)
    database.enqueue(project["id"], "run", run_id=b["id"])
    assert worker.once()
    assert database.get_run(project["id"], b["id"])["status"] == "paused"
    monkeypatch.setattr(database, "save_checkpoint", save)
    worker.stopping = False
    database.command(project["id"], b["id"], "resume", {})
    assert worker.once()
    left, right = [database.load_checkpoint(project["id"], r["id"]) for r in (a, b)]
    assert left[1].digest == right[1].digest
    assert left[0]["context"]["environment"] == right[0]["context"]["environment"]
    with database.tx(project["id"]) as db:

        def recorded(run):
            return db.execute(
                "SELECT time_us,payload FROM events WHERE run_id=%s AND kind='input_delivered' ORDER BY time_us",
                (run["id"],),
            ).fetchall()

        inputs = recorded(a)
        assert inputs == recorded(b)
        assert all(not 53000 <= int(r["time_us"]) < 124000 for r in inputs)
        assert any(int(r["time_us"]) >= 124000 for r in inputs)
        assert all(len(r["payload"]["channels"]) <= 2 for r in inputs)


def test_saturation_phase_coverage_and_censored_settling():
    phases = {"phases": [{"name": "quiet", "duration_s": 1, "input_enabled": False}]}
    rows = [
        {
            "time_us": str(t),
            "elapsed_us": str(t),
            "activation": 1.0,
            "mean_activation": 1.0,
            "saturated_fraction": 1.0,
            "active_fraction": 1.0,
            "edge_density": 0.5,
            "mean_weight": 0.1,
        }
        for t in [*range(0, 1000000, 100000), 999999, 1000000]
    ]
    evidence = phase_evidence(rows, phases)[0]
    assert evidence["complete"]
    assert evidence["endpoints"]["saturated_fraction_time_mean"] == pytest.approx(1)
    assert evidence["settling"]["right_censored"] and evidence["settling"]["time_s"] is None
    for row in rows[3:-1]:
        row["mean_activation"] = 0.0
    # A recovery impulse AT the next phase origin is not part of withdrawal.
    assert rows[-1]["mean_activation"] == 1
    assert phase_evidence(rows, phases)[0]["settling"]["time_s"] == 0.3
    assert "phase.quiet.settling_time_s" not in summarize(rows, phases)
    incomplete = phase_evidence(rows[:-2], phases)[0]
    assert not incomplete["complete"]
    assert incomplete["endpoints"]["mean_activation_time_mean"] is None
    assert incomplete["settling"]["right_censored"]
