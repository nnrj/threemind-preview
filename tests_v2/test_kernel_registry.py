import json

import pytest

from threemind_core import Config, Engine, StateImage, Stimulus
from threemind_kernels.contract import Kernel
from threemind_kernels.definition import KernelDefinition
from threemind_kernels.registry import BASELINE_KERNEL, DEFAULT_KERNEL, kernel_catalog
from threemind_runtime.host import create_engine


def test_legacy_default_factory_preserves_state_and_interface():
    old, selected = Engine(), create_engine(Config(), backend="reference")
    assert isinstance(selected, Kernel)
    assert selected.capture_state().digest == old.capture_state().digest
    for instance in (old, selected):
        instance.inject(Stimulus(0, ((1, 0.4), (2, 0.7))))
        instance.advance_to(113_571)
    assert selected.capture_state().digest == old.capture_state().digest
    restored = create_engine(state=selected.capture_state(), backend="reference")
    assert restored.capture_state().digest == selected.capture_state().digest


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_definition_executes_same_legacy_kernel(backend):
    definition = KernelDefinition.default(config=Config(inhibition=False))
    assert (
        definition.create(backend=backend).capture_state().digest
        == create_engine(
            Config(inhibition=False),
            kernel_id=BASELINE_KERNEL,
            backend=backend,
        )
        .capture_state()
        .digest
    )


def test_definition_normalizes_defaults_but_preserves_scientific_choices():
    original = KernelDefinition.default()
    minimal = original.to_dict()
    minimal["config"] = {}
    assert KernelDefinition.parse(minimal).digest == original.digest
    minimal["config"]["inhibition"] = False
    assert KernelDefinition.parse(minimal).digest != original.digest
    assert original.to_dict()["config"]["inhibition"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"code": "print('arbitrary code')"},
        {"operators": [{"id": "python.eval/1", "phase": "hybrid-event-clock"}]},
        {"operators": []},
        {"kernel_id": "threemind.causal/999"},
        {"state_schema": "threemind.state/5"},
        {"hypothesis_id": "unrelated"},
        {"config": {"invented_answer": "pinecone"}},
    ],
)
def test_definition_rejects_unbound_mechanisms(change):
    document = KernelDefinition.default().to_dict() | change
    with pytest.raises(ValueError):
        KernelDefinition.parse(document)


def test_definition_rejects_duplicate_keys_nonfinite_values_and_direct_construction():
    for raw in (b'{"schema":1,"schema":2}', b'{"schema":NaN}', b"[]", b"x" * 1_048_577):
        with pytest.raises(ValueError):
            KernelDefinition.parse(raw)
    with pytest.raises(ValueError):
        KernelDefinition(b"{}").create(backend="reference")


def test_restore_cannot_silently_convert_or_override_config():
    image = Engine().capture_state()
    with pytest.raises(ValueError, match="saved configuration"):
        create_engine(Config(inhibition=False), state=image, backend="reference")
    with pytest.raises(ValueError, match="unsupported kernel"):
        create_engine(state=image, kernel_id="threemind.unknown/1", backend="reference")
    altered = image.to_dict() | {"schema": "threemind.state/5"}
    with pytest.raises(ValueError, match="state schema"):
        create_engine(state=StateImage.from_dict(altered), backend="reference")
    with pytest.raises(ValueError, match="no automatic fallback"):
        create_engine(backend="unavailable")


def test_catalog_is_a_detached_description():
    a = kernel_catalog()
    a[0]["mechanisms"].clear()
    assert kernel_catalog()[0]["mechanisms"]
    assert sum(k["default"] for k in kernel_catalog()) == 1


def test_lab_protocol_binds_kernel_and_normalizes_legacy_specs():
    from threemind_lab.configuration import validate_configuration
    from threemind_lab.protocols import RunSpec

    assert RunSpec().kernel_id == BASELINE_KERNEL
    normalized = validate_configuration({"environment": "manual"})
    assert normalized["valid"]
    assert normalized["spec"]["kernel_id"] == DEFAULT_KERNEL
    invalid = validate_configuration({"environment": "manual", "kernel_id": "unknown"})
    assert not invalid["valid"]
    assert "unsupported kernel" in invalid["errors"][0]["message"]


def test_principle_documents_are_published_with_original_text():
    from threemind_lab.config import ROOT
    from threemind_lab.documents import Documents

    library = Documents(ROOT)
    for language in ("zh", "en"):
        doc = library.read(f"docs/{language}/kernel-evolution-principles.md")
        assert doc["category"] == "principles"
        assert "ThreeMind 把对生物机制的模拟作为一条可行路线" in doc["markdown"]
    assert library.read("docs/zh/plans/multi-kernel-implementation.md")["category"] == "plans"


def test_baseline_manifest_is_bound_to_frozen_witness_and_hypotheses():
    import hashlib
    from pathlib import Path

    preserved = kernel_catalog()[0]["baseline"]
    raw = (Path(__file__).parent / "fixtures/causal9-baseline.json").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == preserved["witness_sha256"]
    assert preserved["kernel_id"] == BASELINE_KERNEL
    assert preserved["revision"].startswith("b53fba1")
    assert "docs/zh/consciousness-hypothesis.md" in {s["path"] for s in preserved["sources"]}


def test_cli_validate_does_not_execute_kernel(tmp_path, monkeypatch, capsys):
    from threemind_kernels.cli import main

    definition = KernelDefinition.default()
    path = tmp_path / "kernel.json"
    path.write_bytes(definition.payload)
    monkeypatch.setattr("sys.argv", ["threemind-kernels", "validate", str(path)])
    monkeypatch.setattr(KernelDefinition, "create", lambda **kw: pytest.fail("validation executed a kernel"))
    main()
    assert json.loads(capsys.readouterr().out)["definition_hash"] == definition.digest


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_new_creation_default_and_old_explicit_choices_are_separate(backend):
    from threemind_kernels.memory import MemoryConfig
    from threemind_lab.configuration import default_spec, validate_configuration
    from threemind_lab.protocols import RunSpec
    from threemind_runtime.ecology_job import parse_job

    created = create_engine(backend=backend).capture_state().to_dict()
    assert created["dynamics"] == DEFAULT_KERNEL == "threemind.continuous-memory/3"
    assert created["config"]["novelty_mode"] == "arrival-window"
    assert default_spec()["kernel_id"] == DEFAULT_KERNEL
    assert default_spec()["activity_readout"]["enabled"]
    assert (
        create_engine(MemoryConfig(), backend=backend).capture_state().to_dict()["dynamics"]
        == "threemind.continuous-memory/1"
    )
    historical = {"environment": "manual", "config": {"inhibition": False}}
    assert RunSpec.model_validate(historical).kernel_id == BASELINE_KERNEL
    assert not RunSpec.model_validate(historical).activity_readout.enabled
    assert parse_job({}).kernel_id == BASELINE_KERNEL
    checked = validate_configuration(historical, current=historical)
    assert checked["valid"] and checked["spec"]["kernel_id"] == BASELINE_KERNEL
    assert not checked["spec"]["activity_readout"]["enabled"]
    old = Engine(Config(inhibition=False)).capture_state()
    assert create_engine(state=old, backend=backend).capture_state().digest == old.digest
