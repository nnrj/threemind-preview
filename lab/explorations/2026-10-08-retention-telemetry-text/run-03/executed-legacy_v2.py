"""User-requested full memory/2 control using the frozen run-02 inputs."""

import gzip
import json
import time
from pathlib import Path

import experiment as study

from threemind_kernels.novelty import NoveltyEngine
from threemind_kernels.novelty_native import NativeNoveltyEngine
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def main():
    source = study.HERE / "run-02"
    old = json.loads((source / "manifest.json").read_bytes())
    for name, digest in old["kernel_sources"].items():
        assert study.sha((study.ROOT / name).read_bytes()) == digest
    assert study.sha(study.NATIVE.read_bytes()) == old["native_sha256"]
    study.CONFIG = TextSensorConfig(**old["text_sensor"])
    assert study.CONFIG.frame_characters == 24
    evidence = study.Evidence(study.HERE / "run-03")
    for name in ("inputs-repeat.json.gz", "inputs-single.json.gz", "curriculum.json"):
        evidence.write(name, (source / name).read_bytes(), raw=True)
    evidence.write("registered-protocol.md", (study.HERE / "protocol-v2.md").read_bytes(), raw=True)
    evidence.write("executed-legacy_v2.py", Path(__file__).read_bytes(), raw=True)
    evidence.write("executed-experiment.py", Path(study.__file__).read_bytes(), raw=True)
    evidence.write(
        "manifest.json",
        old
        | {
            "schema": "threemind.retention-telemetry-text-v2/1",
            "parent_manifest_sha256": study.sha((source / "manifest.json").read_bytes()),
            "registered_protocol": "protocol-v2.md",
            "registered_protocol_sha256": study.sha((study.HERE / "protocol-v2.md").read_bytes()),
            "runner_sha256": study.sha(Path(__file__).read_bytes()),
            "shared_instrument_sha256": study.sha(Path(study.__file__).read_bytes()),
            "kernel_id": "threemind.continuous-memory/2",
            "main_subjects": 2,
            "defaults_exception": {"quiescence_death_us": 10**12},
        },
    )
    events = {
        kind: json.loads(gzip.decompress((source / f"inputs-{kind}.json.gz").read_bytes()))
        for kind in ("repeat", "single")
    }
    start = time.perf_counter()
    a = study.create("full-v2", events["repeat"], NoveltyEngine)
    b = study.create("full-v2", events["repeat"], NativeNoveltyEngine)
    for t in (1_000_001, 6_000_000, 12_000_000, 24_000_000):
        a.advance_to(t)
        b.advance_to(t)
        study.close(a.capture_state().to_dict(), b.capture_state().to_dict())
        study.close(a.graph(), b.graph())
    for e in (a, b):
        restored = type(e)(state=e.capture_state())
        e.advance_to(24_117_771)
        restored.advance_to(24_117_771)
        assert e.capture_state().digest == restored.capture_state().digest
    validation = {
        "mode": "full-v2",
        "full_state_matches": True,
        "same_backend_restore_exact": True,
        "until_us": "24000000",
        "wall_seconds": time.perf_counter() - start,
    }
    evidence.write("backend-validation.json", validation)
    print(json.dumps(validation), flush=True)
    sensor = TextSensor(study.SEED, study.CONFIG)
    results = [
        study.run(evidence, "full-v2", kind, events[kind], sensor, set(old["text_channels"]), old["input_hashes"][kind])
        for kind in ("repeat", "single")
    ]
    evidence.write(
        "results.json",
        {
            "schema": "threemind.retention-telemetry-text-v2/1",
            "runs": results,
            "wall_seconds": time.monotonic() - evidence.start,
            "bytes_before_summary": evidence.bytes,
        },
    )
    evidence.write(
        "checksums.json",
        {
            p.relative_to(evidence.directory).as_posix(): study.sha(p.read_bytes())
            for p in sorted(evidence.directory.rglob("*"))
            if p.is_file()
        },
    )
    print(json.dumps({"complete": True, "subjects": 2, "evidence_bytes": evidence.bytes}), flush=True)


if __name__ == "__main__":
    main()
