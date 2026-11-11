"""Pin source identities and small current-baseline witnesses before adapter changes."""

import hashlib
import json
import subprocess
from pathlib import Path

from threemind_core import Stimulus
from threemind_runtime import create_engine
from threemind_runtime.sensory import TextSensor, TextSensorConfig

ROOT = Path(__file__).resolve().parents[1]
REVISION = "6241016"


def witnesses():
    output = {}
    for name, channels, intensity in (
        ("normal", ((17, 1.0), (31, 0.5)), 1),
        ("equal-drive-strong", ((17, 0.25), (31, 0.125)), 4),
        ("strong", ((17, 1.0), (31, 0.5)), 4),
    ):
        engine = create_engine(kernel_id="threemind.continuous-memory/2", backend="reference")
        engine.inject(Stimulus(0, channels, intensity))
        points = []
        for now in (0, 100000, 1000000):
            engine.advance_to(now)
            points.append({"time_us": now, "digest": engine.capture_state().digest})
        output[name] = points
    output["text"] = [f["stimulus"].to_dict() for f in TextSensor(7, TextSensorConfig()).frames("甲是松子。", 1)]
    return output


if __name__ == "__main__":
    paths = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            REVISION,
            "src/threemind_core",
            "src/threemind_kernels",
            "src/threemind_runtime",
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    sources = {
        p: hashlib.sha256(subprocess.check_output(["git", "show", f"{REVISION}:{p}"], cwd=ROOT)).hexdigest()
        for p in paths
        if p.endswith(".py")
    }
    for path, sha in sources.items():
        if path.startswith(("src/threemind_core/", "src/threemind_kernels/")):
            assert hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == sha, path
    result = {"revision": REVISION, "sources": sources, "witnesses": witnesses()}
    destination = ROOT / "tests_v2/fixtures/stimulus-6241016.json"
    with destination.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    print(destination)
