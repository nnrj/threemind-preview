import json

import pytest

from threemind_transformer.language_protocol import LanguageProtocol, LanguageTraining, ScratchTraining
from threemind_transformer.language_session import LanguageSession


def test_raw_language_bus_continuation_and_readonly_output():
    protocol = LanguageProtocol(response_us=100000)
    session = LanguageSession(protocol.model_dump(), backend="reference")
    first = session.turn("甲是松子。")
    assert first["process"]["has_activity"]
    assert first["interpretation"]["text"] is None
    image, context = session.engine.capture_state(), json.loads(json.dumps(session.context()))
    clone = LanguageSession(protocol.model_dump(), image=image, context=context, backend="reference")
    left, right = session.turn("乙是铃铛。"), clone.turn("乙是铃铛。")
    assert left["after_hash"] == right["after_hash"]
    assert left["process"] == right["process"]
    with pytest.raises(ValueError, match="frozen adapter"):
        LanguageSession(protocol.model_copy(update={"seed": 18}).model_dump(), image=image, context=context)


def test_scratch_model_determinism_learning_and_no_pretrained_weights(tmp_path):
    pytest.importorskip("torch")
    from threemind_transformer import language_model
    from threemind_transformer.scratch_language import load, train

    protocol = LanguageProtocol(
        input_model="scratch",
        output_model="scratch",
        mode="strict",
        scratch_width=32,
        scratch_layers=1,
        embedding_dimensions=32,
        maximum_tokens=32,
    )
    encoded = language_model.encode(["甲是松子。"], protocol, "cpu", lambda: None)
    assert not encoded["pretrained_weights"]
    assert encoded == language_model.encode(["甲是松子。"], protocol, "cpu", lambda: None)
    artifact = tmp_path / "scratch.safetensors"
    spec = ScratchTraining(protocol=protocol, texts=["甲是松子。", "乙是铃铛。"], steps=2)
    result = train(spec, artifact, "cpu", lambda: None)
    assert result["loss_samples"][0]["loss"] > 0
    trained = protocol.model_copy(update={"input_checkpoint_sha256": result["checkpoint_sha256"]})
    from threemind_transformer.language_bundle import pack, unpack

    portable = LanguageSession(trained.model_dump(), backend="reference")
    restored, assets = unpack(
        pack(portable.engine.capture_state(), portable.context(), {"input": artifact.read_bytes()}), backend="reference"
    )
    assert restored.protocol == trained and assets["input"] == artifact.read_bytes()
    assert (
        language_model.encode(["甲是松子。"], trained, "cpu", lambda: None, artifact)["vectors"] != encoded["vectors"]
    )
    with pytest.raises(ValueError, match="identity"):
        load(trained, "input", "cpu")
    head = tmp_path / "head.safetensors"
    samples = [{"features": [0.1] * 256, "text": "甲"}, {"features": [0.2] * 256, "text": "乙"}]
    result = language_model.train(
        LanguageTraining(protocol=protocol, samples=samples, steps=2, train_decoder=True), head, "cpu", lambda: None
    )
    assert not result["base_model_frozen"]
    decoded = language_model.decode(samples[0]["features"], protocol, head, "cpu", lambda: None)
    assert len(decoded["output_tokens"]) <= 32
    assert "incoming_user_text" not in decoded["decoder_exposure"]
    batched = language_model.decode_many(
        [samples[0]["features"], samples[1]["features"], samples[0]["features"]],
        protocol,
        head,
        "cpu",
        lambda: None,
    )
    assert batched["shared_generation_context"] is False
    assert batched["windows"][0] == batched["windows"][2] == decoded
    assert batched["windows"][1] == language_model.decode(samples[1]["features"], protocol, head, "cpu", lambda: None)
    with pytest.raises(ValueError, match="strict decoder"):
        language_model.decode(samples[0]["features"], protocol, head, "cpu", lambda: None, assistance="answer")


def test_no_silent_scratch_truncation_or_fictional_activity():
    with pytest.raises(ValueError, match="no truncation"):
        ScratchTraining(protocol=LanguageProtocol(input_model="scratch", scratch_context=64), texts=["甲" * 30])
    from threemind_transformer.language_senses import ProcessFeatures

    class Engine:
        time_us = 0

        def observation_nodes(self):
            return []

    observer = ProcessFeatures(LanguageProtocol(), 0, 10000)
    observer.sample(Engine())
    assert observer.result()["censored"]
    assert not observer.result()["has_activity"]


def test_cli_recovers_with_the_same_mapping_and_refuses_overwriting(tmp_path):
    from threemind_transformer.language_cli import main

    protocol = tmp_path / "language.json"
    protocol.write_text(LanguageProtocol(response_us=100000).model_dump_json(), encoding="utf-8-sig")
    store = tmp_path / "session.sqlite"
    arguments = [
        "turn",
        "--protocol",
        str(protocol),
        "--store",
        str(store),
        "--text",
        "甲是松子。",
        "--backend",
        "reference",
    ]
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    main(arguments + ["--output", str(first)])
    main(arguments + ["--resume", "--output", str(second)])
    assert json.loads(second.read_text(encoding="utf-8"))["revision"] == 2
    with pytest.raises(FileExistsError):
        main(arguments + ["--resume", "--output", str(first)])


def test_disabled_observers_do_not_change_core_and_manual_turn_triggers_temporal_windows():
    protocol = LanguageProtocol(response_us=100000)
    observed = LanguageSession(protocol.model_dump(), backend="reference")
    hidden = LanguageSession(
        protocol.model_dump(),
        backend="reference",
        readouts={
            "structural_readout": {"enabled": False},
            "temporal_readout": {"enabled": False},
            "activity_readout": {"enabled": False},
        },
    )
    left, right = observed.turn("甲是松子。"), hidden.turn("甲是松子。")
    assert left["after_hash"] == right["after_hash"]
    assert observed.reader.host.temporal.windows


@pytest.mark.parametrize("kernel_id", [None, "threemind.continuous-memory/5.1"])
def test_portable_language_device_roundtrip_and_checksum(kernel_id):
    import io
    import zipfile

    from threemind_transformer.language_bundle import pack, unpack

    session = LanguageSession(LanguageProtocol(response_us=100000).model_dump(), backend="reference", kernel_id=kernel_id)
    session.turn("甲是松子。")
    raw = pack(session.engine.capture_state(), session.context())
    restored, assets = unpack(raw, backend="reference")
    assert not any(assets.values())
    assert session.turn("甲是")["after_hash"] == restored.turn("甲是")["after_hash"]
    broken = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(broken, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name) + (b" " if name == "context.json" else b""))
    with pytest.raises(ValueError, match="checksum"):
        unpack(broken.getvalue())


def test_owned_process_memory_includes_virtualenv_child_and_stops_it():
    import subprocess
    import sys
    import time

    from threemind_transformer.process_guard import OwnedProcessTree

    script = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; data=bytearray(64*2**20); time.sleep(15)']); time.sleep(15)"
    child = subprocess.Popen([sys.executable, "-c", script], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    tree = OwnedProcessTree(child.pid)
    try:
        deadline = time.monotonic() + 10
        peak = 0
        while peak < 64 * 2**20 and time.monotonic() < deadline:
            peak = max(peak, tree.sample())
            time.sleep(0.05)
        assert peak >= 64 * 2**20
        assert len(tree.known) >= 2
    finally:
        tree.stop()
        child.wait(timeout=5)
    assert not any(p.is_running() for p in tree.known.values())
