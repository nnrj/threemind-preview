"""Standalone Rust persistence preserves the real historical /5.2 identity."""

import os
from pathlib import Path
import subprocess
import pytest
from threemind_core import Stimulus
from threemind_kernels.local52 import Local52Config, Local52Engine
from threemind_runtime import ArtifactCodec
from test_local53 import same


@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic"))
@pytest.mark.parametrize("fmt", ("json", "tmind"))
def test_standalone_roundtrip(curve, fmt, tmp_path):
    a = Local52Engine(Local52Config(decay_curve=curve, retention_relaxation_enabled=False))
    for t in (0, 100_000, 900_000):
        a.inject(Stimulus(t, ((1, 0.5), (2, 0.3))))
    a.advance_to(137_001)
    state = a.capture_state()
    raw = ArtifactCodec.encode(state, fmt)
    src = tmp_path / ("in." + fmt)
    src.write_bytes(raw)
    out = tmp_path / "out.tmind"
    db = tmp_path / "subject.sqlite"
    runtime = os.environ.get("THREEMIND_TEST_RUNTIME", str(Path.cwd() / "target/release/threemind-runtime.exe"))
    p = subprocess.run(
        [
            runtime,
            "--model",
            str(src),
            "--clock",
            "unbounded",
            "--until-us",
            "1200000",
            "--export",
            str(out),
            "--store",
            str(db),
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    a.advance_to(1_200_000)
    same(a.capture_state().to_dict(), ArtifactCodec.decode(out.read_bytes()).to_dict())
    assert src.read_bytes() == raw
    final = tmp_path / "final.json"
    p = subprocess.run(
        [
            runtime,
            "--resume",
            "--store",
            str(db),
            "--clock",
            "unbounded",
            "--until-us",
            "2000000",
            "--export",
            str(final),
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    a.advance_to(2_000_000)
    same(a.capture_state().to_dict(), ArtifactCodec.decode(final.read_bytes()).to_dict())
