"""One internal second per fresh engineering world; all outputs are excluded from the study."""
from datetime import datetime, timezone
from time import monotonic
from apparatus import *
from lab.tools.ocean_evolution_cli import RecordWriter
from lab.tools.ocean_contact_cli import save

def main():
    folder = ROOT / ".work" / ("ocean63-pilot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    folder.mkdir()
    print(folder, flush=True)
    for key, world in (("E28", Primitive63(primitive(7))), ("E30", Contact63(contact(7, "core"))),
                       ("E38", enclosure(E37_INPUT))):
        out = folder / key
        out.mkdir()
        writer = RecordWriter(out / "inputs", chunk_steps=25)
        started = monotonic()
        for _ in range(50):
            world.step(writer.record)
        writer.flush()
        elapsed = monotonic() - started
        save(world, out / "checkpoint")
        metrics = world.metrics()
        child = create_engine(state=newborn_without_endowment(world.engines[0].capture_state()), backend="native")
        assert child.metrics()["energy"]["reserve"] == 0
        path = out / "measure.json"
        result = dict(wall_seconds=elapsed, simulated_seconds=1, founders=len(world.bodies),
                      input_bytes=sum(p.stat().st_size for p in (out/"inputs").glob("*")),
                      checkpoint_bytes=sum(p.stat().st_size for p in (out/"checkpoint").glob("*")),
                      balance_error=metrics["energy_balance_error"], kernel=child.metrics()["kernel_id"])
        path.write_text(json.dumps(result), encoding="utf8")
        print(key, result, flush=True)

if __name__ == "__main__":
    main()
