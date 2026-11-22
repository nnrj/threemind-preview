"""Engineering preflight on matching ocean conditions for the registered 5.1 cost guard."""
import gzip
import json
import statistics
from datetime import datetime, timezone
from time import monotonic

from apparatus import *
from lab.tools.ocean_evolution_cli import RecordWriter
from threemind_runtime.codec import ArtifactCodec

OLD = "threemind.continuous-memory/5.1"


def measure(folder, version):
    # A different seed and an engineering cohort. Formal worlds start separately.
    w = Contact63(contact(7, "core"))
    if version == OLD:
        w.engines = {i: create_engine(w._config(seed), kernel_id=OLD, backend="native")
                     for i, seed in w.seeds.items()}
    assert all(e.metrics()["kernel_id"] == version for e in w.engines.values())
    start = monotonic()
    folder.mkdir()
    writer = RecordWriter(folder / "inputs", chunk_steps=50)
    for _ in range(150):
        w.step(writer.record)
    writer.flush()
    wall = monotonic() - start
    input_bytes = sum(p.stat().st_size for p in (folder / "inputs").iterdir())
    with gzip.open(folder / "terminal.jsonl.gz", "wb", compresslevel=3) as raw:
        raw.write(json.dumps(w.capture(), separators=(",", ":")).encode() + b"\n")
        for i, e in w.engines.items():
            raw.write(e.capture_state().payload + b"\n")
    return dict(kernel=version, seconds=wall, inputs=input_bytes,
                end_bytes=(folder/"terminal.jsonl.gz").stat().st_size,
                total_bytes=input_bytes+(folder/"terminal.jsonl.gz").stat().st_size)


def main():
    out = ROOT / ".work" / ("ocean63-cost-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    out.mkdir()
    print(out, flush=True)
    rows = []
    for n, version in enumerate((OLD, KERNEL, KERNEL, OLD, OLD, KERNEL)):
        row = measure(out / str(n), version)
        print(n, row, flush=True)
        rows.append(row)
        (out/"measurements.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
    stats = {k: statistics.median(r[k] for r in rows if r["kernel"] == KERNEL) /
                statistics.median(r[k] for r in rows if r["kernel"] == OLD)
             for k in ("seconds", "inputs", "end_bytes", "total_bytes")}
    (out/"ratios.json").write_text(json.dumps(stats, indent=2), encoding="utf8")
    print(stats, flush=True)


if __name__ == "__main__":
    main()
