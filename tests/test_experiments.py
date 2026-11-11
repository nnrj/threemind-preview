import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind.ai import ChatClient
from threemind.experiments import ExperimentController, ExperimentError, ExperimentStore
from threemind.manager import RuntimeManager
from threemind.persistence import FileBackend
from threemind.runtime import ConsciousnessRuntime


def _controller(tmp_path: Path) -> tuple[ExperimentController, RuntimeManager]:
    runtime = ConsciousnessRuntime()
    manager = RuntimeManager(runtime)
    store = ExperimentStore(lambda: FileBackend(tmp_path / "records.json"))

    def submit(item: ConsciousnessRuntime, text: str, intensity: float, source: str):
        item.events.append({"kind": "experiment_stimulus", "text": text, "intensity": intensity, "source": source})
        return {"accepted": True, "source": source, "text": text}

    controller = ExperimentController(
        manager=manager,
        store=store,
        provider_lookup=lambda _provider_id: None,
        ai_client=ChatClient(),
        submit_stimulus=submit,
        graph_view=lambda item, limit: item.graph(limit),
        prepare_runtime=lambda _item: None,
        snapshot_capture=lambda item, label, reason: {"label": label, "reason": reason, "tick": item.tick},
        checkpoint_history=lambda _item: None,
        lab_directory=tmp_path / "lab",
    )
    return controller, manager


def test_experiment_plan_rejects_unregistered_command(tmp_path: Path) -> None:
    controller, manager = _controller(tmp_path)
    try:
        run = controller.create_run(target_id=manager.active_id, title="safe", sandbox=False)
        try:
            controller.set_plan(run["id"], [{"op": "archive.delete", "args": {"path": "anything"}}])
        except ExperimentError as error:
            assert "not permitted" in str(error)
        else:
            raise AssertionError("unregistered command was accepted")
    finally:
        manager.stop_all()


def test_experiment_sandbox_and_audit_record(tmp_path: Path) -> None:
    controller, manager = _controller(tmp_path)
    try:
        run = controller.create_run(target_id=manager.active_id, title="sandbox", sandbox=True, background_mode="paused")
        assert run["target"]["sandbox"] is True
        assert run["target"]["runtime_id"] != manager.active_id
        saved = controller.set_plan(run["id"], [{"op": "observe.summary"}, {"op": "experiment.note", "args": {"text": "researcher note"}}])
        assert len(saved["plan"]) == 2
        partial = controller.execute_step(run["id"], saved["plan"][0]["id"])
        assert partial["steps"][0]["op"] == "observe.summary"
        assert partial["status"] == "partial"
        completed = controller.execute_step(run["id"], saved["plan"][1]["id"])
        assert completed["status"] == "completed"
        analyzed = controller.analyze(run["id"], prompt="separate observation from inference")
        assert analyzed["analysis"][-1]["researcher_focus"] == "separate observation from inference"
        assert controller.get_run(run["id"])["title"] == "sandbox"
    finally:
        manager.stop_all()
