"""Run with python -I -S and an isolated wheel install to verify the deployment boundary."""

import importlib.util
import json
import sys
from pathlib import Path

installed = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(installed))
for package in ("threemind_lab", "fastapi", "psycopg"):
    assert importlib.util.find_spec(package) is None, package

from threemind_core import Stimulus
from threemind_kernels.registry import kernel_catalog
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.deployment import declare, verify
from threemind_runtime.host import create_engine

results = []
for kernel in kernel_catalog():
    identity = kernel["kernel_id"]
    engine = create_engine(kernel_id=identity, backend="reference")
    engine.inject(Stimulus(0, ((1, 0.9), (2, 0.5))))
    engine.inject(Stimulus(70_000, ((1, 0.4), (3, 0.4))))
    engine.inject(Stimulus(150_000, ((1, 0.8),)))
    engine.advance_to(100_000)
    package = ArtifactCodec.encode(engine.capture_state(), "json")
    verify(package, declare(package))
    restored = create_engine(state=ArtifactCodec.decode(package), backend="reference")
    for replica in (engine, restored):
        replica.advance_to(300_000)
    assert engine.capture_state().digest == restored.capture_state().digest
    results.append({"kernel": identity, "restore_exact": True, "digest": engine.capture_state().digest})
print(json.dumps({"lab_importable": False, "third_party_site_packages": False, "kernels": results}, indent=2))
