import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from test_ecology_runtime import configuration

from threemind_core import Stimulus
from threemind_kernels.registry import BASELINE_KERNEL
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.ecology_job import EcologyJob
from threemind_runtime.population_bundle import PopulationBundle, export_bundle
from threemind_runtime.population_store import PopulationStore

ROOT = Path(__file__).resolve().parents[1]


def cli(*args, success=True):
    program = "import runpy,sys; runpy.run_module('threemind_runtime.ecology_cli',run_name='__main__'); assert not any(n.startswith('threemind_lab') for n in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", program, *map(str, args)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
        check=False,
    )
    if success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
    return result


def test_cli_store_bundle_and_uninterrupted_population_match_without_lab(tmp_path):
    protocol = tmp_path / "protocol.json"
    job = EcologyJob(ecology=configuration())
    protocol.write_text(job.model_dump_json(), encoding="utf-8")
    local = tmp_path / "population.sqlite"
    half, final, imported = (tmp_path / name for name in ("half.zip", "final.zip", "imported.zip"))
    evidence = tmp_path / "evidence.jsonl"
    first = cli(
        "--protocol",
        protocol,
        "--store",
        local,
        "--until-us",
        17000,
        "--clock",
        "unbounded",
        "--export",
        half,
        "--evidence",
        evidence,
    )
    assert json.loads(first.stdout)["time_us"] == 17000
    cli("--store", local, "--resume", "--until-us", 100000, "--clock", "unbounded", "--export", final)
    cli("--bundle", half, "--until-us", 100000, "--clock", "unbounded", "--export", imported)
    with PopulationBundle(final) as from_store, PopulationBundle(imported) as from_bundle, job.open() as plain:
        plain.advance_to(100000)
        expected = plain.checkpoint()
        assert expected == from_store.checkpoint == from_bundle.checkpoint
        assert len(expected[1]) == 6
    rows = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "invocation" and rows[0]["start_us"] == 0
    assert any(row["kind"] == "input_scheduled" and row["scope"] == "individual" for row in rows)
    store = PopulationStore(local)
    revision, _, _ = store.load("ecology")
    saved = list(store.evidence("ecology", revision))
    assert any(row["kind"] == "input_delivered" for row in saved)
    assert len([row for row in saved if row["kind"] == "individual_born"]) == 4
    cli("--resume", "--store", local, "--founder", final, success=False)
    cli("--protocol", protocol, "--export", protocol, success=False)
    unwanted = tmp_path / "invalid-evidence.jsonl"
    refused = cli("--resume", "--store", local, "--until-us", 1, "--evidence", unwanted, success=False)
    assert "precedes" in refused.stderr and not unwanted.exists()


def test_population_bundle_rejects_missing_undeclared_and_corrupt_models(tmp_path):
    job = EcologyJob(ecology=configuration())
    valid = tmp_path / "valid.zip"
    with job.open() as runtime:
        runtime.advance_to(20000)
        export_bundle(valid, job, runtime.checkpoint())
    original = valid.read_bytes()
    with job.open() as runtime:
        metadata, images = runtime.checkpoint()
        metadata["time_us"] += 1
        with pytest.raises(ValueError, match="checksum"):
            export_bundle(tmp_path / "invalid.zip", job, (metadata, images))
        assert not (tmp_path / "invalid.zip").exists()
    with pytest.raises(FileExistsError), PopulationBundle(valid) as package:
        export_bundle(valid, package.protocol, package.checkpoint)
    assert valid.read_bytes() == original
    with zipfile.ZipFile(valid) as source:
        files = {name: source.read(name) for name in source.namelist()}
    for name, alteration in (
        ("missing", {key: value for key, value in files.items() if key != "models/n0.tmind"}),
        ("path", files | {"../undeclared": b"no extraction"}),
        ("corrupt", files | {"models/n0.tmind": files["models/n2.tmind"]}),
    ):
        path = tmp_path / f"{name}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for entry, value in alteration.items():
                archive.writestr(entry, value)
        with (
            pytest.raises((ValueError, KeyError)),
            PopulationBundle(path) as package,
            package.protocol.open(checkpoint=package.checkpoint),
        ):
            pass
    assert not (tmp_path.parent / "undeclared").exists()


def test_cli_example_and_numerical_boundary_recording(tmp_path):
    example = tmp_path / "example.json"
    cli("--write-example", example)
    job = EcologyJob.model_validate_json(example.read_text(encoding="utf-8"))
    # The example follows the user's creation default; this historical runtime
    # fixture explicitly tests the original ecology kernel.
    job = EcologyJob.model_validate_json(json.dumps(job.model_dump() | {"kernel_id": BASELINE_KERNEL, "core_config": {}}))
    job.participant.trace = True
    example.write_text(job.model_dump_json(), encoding="utf-8")
    refused = cli("--protocol", example, "--until-us", 20000, success=False)
    assert "requires --store" in refused.stderr
    local = tmp_path / "trace.sqlite"
    cli("--protocol", example, "--store", local, "--until-us", 30000, "--clock", "unbounded")
    with PopulationStore(local).connect() as db:
        rows = db.execute("SELECT metadata_json FROM population_checkpoints ORDER BY revision").fetchall()
    assert [json.loads(row[0])["time_us"] for row in rows] == [0, 10000, 20000, 30000]


def test_founder_import_preserves_nondefault_sensory_profile_and_real_birth(tmp_path):
    from threemind_runtime.inheritance import birth

    job = EcologyJob()
    profile = job.profile
    profile["text_sensor"]["max_carrier_characters"] = 321
    profile["acoustic_output"]["maximum_voices"] = 7
    engine = create_engine(kernel_id=BASELINE_KERNEL)
    engine.inject(Stimulus(1000, ((12345, 0.9), (67890, 0.7))))
    engine.advance_to(20000)
    model = tmp_path / "founder.tmind"
    model.write_bytes(ArtifactCodec.encode(engine.capture_state(), "tmind", profile=profile))
    default = tmp_path / "default.json"
    default.write_text(job.model_dump_json(), encoding="utf-8")
    refused = cli("--protocol", default, "--founder", model, "--until-us", 0, success=False)
    assert "profile must be preserved" in refused.stderr
    adopted = tmp_path / "adopted.json"
    cli("--write-example", adopted, "--founder", model)
    saved = EcologyJob.model_validate_json(adopted.read_text(encoding="utf-8"))
    assert saved.profile == profile and saved.participant.acoustic_output.maximum_voices == 7
    bundle = tmp_path / "born.zip"
    cli("--protocol", adopted, "--founder", model, "--until-us", 0, "--export", bundle)
    with PopulationBundle(bundle) as package:
        assert package.protocol.profile == profile
        assert all(image.digest == birth(engine.capture_state()).digest for image in package.images.values())
