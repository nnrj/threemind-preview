"""Restore every saved state and replay bounded, explicitly reported intervals."""

import argparse
import hashlib
import json
import time

from experiment import ROOT, VERIFICATION_SECONDS, WORK, active_workers, check_study, study

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_evolution_cli import iter_records, load_population
from lab.tools.ocean_interventions import make_control
from lab.tools.ocean_view import recorded_segments


def snapshots(part):
    values = [part / "initial"]
    values += sorted((part / "checkpoints").glob("*"), key=lambda p: int(p.name))
    values.append(part / "final")
    return {read_json(p / "manifest.json")["context"]["time_us"]: p for p in values}


def files_digest(paths):
    digest = hashlib.sha256()
    for base in sorted(paths):
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            name = path.relative_to(WORK).as_posix().encode()
            digest.update(len(name).to_bytes(8, "big") + name)
            digest.update(path.stat().st_size.to_bytes(8, "big"))
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
    return digest.hexdigest()


def saved_state_digest(root):
    return files_digest(
        [p for part in recorded_segments(root) for p in (part / "initial", part / "checkpoints", part / "final")]
    )


def replay_interval(part, start, end, *, guard):
    paths = snapshots(part)
    world = load_population(paths[start])
    count = 0
    tick = time.monotonic()
    for expected in iter_records(part / "inputs"):
        if expected["time_us"] <= start:
            continue
        if expected["time_us"] > end:
            break
        if count % 50 == 0:
            guard()
        observed = []
        world.step(observed.append)
        if observed != [expected]:
            raise AssertionError(f"replay differs at {part.name}:{expected['time_us']}")
        count += 1
    assert world.time_us == end
    assert world.capture() == load_population(paths[end]).capture()
    return {
        "segment": str(part.relative_to(WORK)),
        "start_us": start,
        "end_us": end,
        "steps": count,
        "matched_inputs_actions_events_and_state": True,
        "wall_seconds": time.monotonic() - tick,
    }


def event_interval(root, kinds):
    for part in recorded_segments(root):
        times = sorted(snapshots(part))
        events = read_json(part / "events.json")
        for e in events:
            if e["kind"] in kinds:
                # Validation selection, not a favorable scientific observation window.
                start = max((t for t in times if t < e["time_us"]), default=None)
                end = min((t for t in times if t >= e["time_us"]), default=None)
                if start is not None and end is not None:
                    return part, start, end
    return None


def main(stage="all"):
    started = time.monotonic()
    prior_receipt = read_json(WORK / "formal-verification-fixed.json") if stage == "supplement" else None
    stopped = WORK / "verification-stopped-attempt.json"
    prior_wall = read_json(stopped)["wall_seconds"] if stopped.exists() else 0
    prior_wall += sum(read_json(p)["wall_seconds"] for p in (WORK / "verification-attempts").glob("*.json"))
    attempt_id = time.time_ns()
    status = "failed"
    progress = WORK / "verification-progress" / stage
    s = study()
    try:
        check_study(s, True)
        for name, sha in read_json(WORK / "apparatus-sources/manifest.json").items():
            assert hashlib.sha256((ROOT / "lab/tools" / name).read_bytes()).hexdigest() == sha
        completed_wall = s.completed_wall
        if completed_wall + VERIFICATION_SECONDS > s.settings.wall_seconds:
            raise RuntimeError("registered validation allowance no longer fits aggregate budget")

        def guard():
            check_study(s)
            elapsed = time.monotonic() - started
            live_wall = sum(
                time.time() - w["started_epoch"]
                for w in active_workers()
                if not (WORK / w["output"] / "result.json").exists()
            )
            if s.completed_wall + live_wall + prior_wall + elapsed > s.settings.wall_seconds:
                raise RuntimeError("aggregate simulation and verification budget")
            if prior_wall + elapsed > VERIFICATION_SECONDS:
                raise RuntimeError("bounded verification time allowance reached")

        worlds = []
        cases = sorted(p.parent for p in (WORK / "cases").glob("*/result.json"))
        if stage != "all":
            cases = [
                p
                for p in cases
                if p.name.startswith(("phase1-", "fork-") if stage == "fixed" else ("confirm-", "control-"))
            ]
        for root in cases:
            guard()
            saved_digest = saved_state_digest(root)
            cached = progress / f"world-{root.name}.json"
            if cached.exists():
                row = read_json(cached)
                assert row["saved_state_digest"] == saved_digest, "saved evidence changed since restoration"
                worlds.append(row)
                print(json.dumps({"reused_restoration": root.name}), flush=True)
                continue
            prior, count, worst = None, 0, 0.0
            for part in recorded_segments(root):
                guard()
                original = load_population(part / "initial").capture()
                if prior is not None:
                    assert original == prior, "continuation changed saved state"
                # Restore all files, including a final that duplicates the last checkpoint time.
                paths = [part / "initial", *(part / "checkpoints").glob("*"), part / "final"]
                for path in paths:
                    guard()
                    restored = load_population(path)
                    # JSON object keys are strings; in-memory individual keys are integers.
                    # Canonicalize serialization only, never relax values or state hashes.
                    assert json.loads(json.dumps(restored.capture())) == read_json(path / "manifest.json")["context"]
                    worst = max(worst, abs(restored.metrics()["energy_balance_error"]))
                    count += 1
                final = load_population(part / "final")
                assert final.time_us == read_json(part / "result.json")["time_us"]
                prior = final.capture()
            receipt = root / "fork-receipt.json"
            if receipt.exists():
                r = read_json(receipt)
                source = WORK / r["source"]
                assert (
                    hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest() == r["source_manifest_sha256"]
                )
                a = load_population(source).capture()
                b = load_population(root / "initial").capture()
                assert {k: v for k, v in a.items() if k != "protocol"} == {
                    k: v for k, v in b.items() if k != "protocol"
                }
                assert b["protocol"] == a["protocol"] | r["protocol_changes"]
            control_receipt = root / "control-receipt.json"
            if control_receipt.exists():
                r = read_json(control_receipt)
                if r["schema"] == "threemind.ocean-control/1":
                    source = WORK / r["source"]
                    assert (
                        hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
                        == r["source_manifest_sha256"]
                    )
                    rebuilt, rebuilt_receipt = make_control(
                        load_population(source),
                        r["operation"],
                        environment_seed=r.get("new_environment_seed"),
                    )
                    assert rebuilt.capture() == load_population(root / "initial").capture()
                    assert json.loads(json.dumps(rebuilt_receipt)) == {
                        k: v for k, v in r.items() if k not in ("source", "source_manifest_sha256")
                    }
            worlds.append(
                {
                    "case": root.name,
                    "snapshots_restored": count,
                    "largest_energy_error": worst,
                    "saved_state_digest": saved_digest,
                    "final_manifest_sha256": hashlib.sha256(
                        (recorded_segments(root)[-1] / "final/manifest.json").read_bytes()
                    ).hexdigest(),
                }
            )
            write_json(cached, worlds[-1])
            print(json.dumps({"restored": root.name, "snapshots": count}), flush=True)
        scopes = []
        for name in () if stage == "supplement" else ("phase1-0-core", "phase1-0-random"):
            part = WORK / "cases" / name
            times = sorted(snapshots(part))
            scopes.append((part, times[0], times[1]))
        continuation_parts = recorded_segments(WORK / "cases/phase1-0-core")[1:]
        if continuation_parts and stage != "supplement":
            part = continuation_parts[0]
            times = sorted(snapshots(part))
            scopes.append((part, times[0], times[1]))
        network_parts = recorded_segments(WORK / "cases/phase1-1-core")[1:]
        if network_parts and stage != "supplement":
            part = network_parts[0]
            times = sorted(snapshots(part))
            scopes.append((part, times[0], times[1]))
        for prefix, kinds in (("ecology", {"birth", "body_engulfed"}), ("sharing", {"resource_exchange"})):
            interval = None
            for root in cases:
                if root.name.endswith("-" + prefix):
                    interval = event_interval(root, kinds)
                    if interval:
                        break
            if interval and interval not in scopes:
                scopes.append(interval)
        control = WORK / "cases/control-0-silence"
        if stage != "fixed" and (control / "result.json").exists():
            times = sorted(snapshots(control))
            scopes.append((control, times[0], times[1]))
        replays = []
        for interval in scopes:
            part, start, end = interval
            selected = snapshots(part)
            evidence_digest = files_digest([selected[start], selected[end], part / "inputs"])
            key = hashlib.sha256(f"{part.relative_to(WORK)}:{start}:{end}".encode()).hexdigest()
            cached = progress / f"replay-{key}.json"
            if cached.exists():
                receipt = read_json(cached)
                assert receipt["evidence_digest"] == evidence_digest, "replay evidence changed"
            else:
                receipt = replay_interval(*interval, guard=guard) | {"evidence_digest": evidence_digest}
                write_json(cached, receipt)
            replays.append(receipt)
            print(json.dumps({"replayed": receipt}), flush=True)
        answer = {
            "apparatus_unchanged": True,
            "worlds": worlds,
            "replays": replays,
            "wall_seconds": time.monotonic() - started,
            "scope": "all saved state restores and continuation/fork boundaries; selected complete checkpoint intervals, not every formal step",
            "stage": stage,
            "prior_verification_wall_seconds": prior_wall,
        }
        suffix = "" if stage == "all" else "-" + stage
        write_json(WORK / f"formal-verification{suffix}.json", answer)
        if stage == "supplement":
            assert not active_workers(), "finish simulations before combining validation receipts"
            combined = prior_receipt | {
                "worlds": prior_receipt["worlds"] + worlds,
                "replays": prior_receipt["replays"] + replays,
                "wall_seconds": prior_wall + answer["wall_seconds"],
                "stage": "combined",
                "components": ["formal-verification-fixed.json", "formal-verification-supplement.json"],
            }
            names = [r["case"] for r in combined["worlds"]]
            assert len(names) == len(set(names)), "verification scopes overlap"
            assert set(names) == {p.parent.name for p in (WORK / "cases").glob("*/result.json")}
            for row in combined["worlds"]:
                final = recorded_segments(WORK / "cases" / row["case"])[-1] / "final/manifest.json"
                assert hashlib.sha256(final.read_bytes()).hexdigest() == row["final_manifest_sha256"]
                assert saved_state_digest(WORK / "cases" / row["case"]) == row["saved_state_digest"]
                guard()
            combined["wall_seconds"] = prior_wall + time.monotonic() - started
            write_json(WORK / "formal-verification.json", combined)
        status = "complete"
        print(json.dumps(answer, indent=2), flush=True)
    finally:
        write_json(
            WORK / "verification-attempts" / f"{attempt_id}.json",
            {"stage": stage, "status": status, "wall_seconds": time.monotonic() - started},
        )
        s.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("all", "fixed", "supplement"), default="all")
    main(parser.parse_args().stage)
