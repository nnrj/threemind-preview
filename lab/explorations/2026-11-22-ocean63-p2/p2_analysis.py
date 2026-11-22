"""Independent event, generation and movement analysis of sealed P2 worlds."""

import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from zipfile import ZipFile

import pyarrow as pa
from p2_paths import SECOND, SEEDS, SUPPLIES, read
from pyarrow import ipc

# isort: split
from execution import encoded
from outcomes import ratio, reproduction, verdict
from p2_turns import GrowingEncounters, family_roots
from turns import MealTurns


def case_outcome(case):
    result = read(case / "result.json")
    members = {m["id"]: m for m in result["members"]}
    with ZipFile(case / "initial.zip") as z:
        initial = json.loads(z.read("world.json"))
    state_hash = hashlib.sha256(encoded(initial["context"])).hexdigest()
    meals = MealTurns()
    movement = GrowingEncounters(initial["protocol"]["side_m"], members)
    events = []
    expected = 0
    milestones = []
    for path in sorted(case.glob("seg-*.zip")):
        with ZipFile(path) as z:
            manifest = json.loads(z.read("manifest.json"))
            if set(z.namelist()) != set(manifest) | {"manifest.json"} or len(set(z.namelist())) != len(z.namelist()):
                raise ValueError("archive inventory " + str(path))
            for name, digest in manifest.items():
                with z.open(name) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                        raise ValueError("archive hash " + name)
            meta = json.loads(z.read("segment.json"))
            if meta["start_us"] != expected or meta["start_hash"] != state_hash:
                raise ValueError("world continuity " + str(path))
            state_hash = meta["end_hash"]
            with ZipFile(io.BytesIO(z.read("end.zip"))) as checkpoint:
                end_context = json.loads(checkpoint.read("world.json"))["context"]
                if hashlib.sha256(encoded(end_context)).hexdigest() != state_hash:
                    raise ValueError("wrong checkpoint")
            observed = []
            for name in sorted(n for n in manifest if n.endswith(".arrow")):
                reader = ipc.open_file(pa.BufferReader(z.read(name)))
                for ix in range(reader.num_record_batches):
                    batch = reader.get_batch(ix)
                    t = batch.column("time_us").to_numpy()
                    if t[0] != expected + 20_000 or not ((t[1:] - t[:-1]) == 20_000).all():
                        raise ValueError("input tick continuity")
                    expected = int(t[-1])
                    ev = [e for text in batch.column("events").to_pylist() for e in json.loads(text)]
                    meals.consume(batch, ev)
                    observed.extend(ev)
            recorded = [json.loads(x) for x in gzip.decompress(z.read("events.jsonl.gz")).splitlines()]
            if expected != meta["end_us"] or observed != recorded:
                raise ValueError("event or time discrepancy")
            kills = iter(e for e in recorded if e["kind"] == "body_engulfed")
            kill = next(kills, None)
            for raw in gzip.decompress(z.read("motion.jsonl.gz")).splitlines():
                t, items = json.loads(raw)
                while kill is not None and kill["time_us"] <= t:
                    movement.kill(kill)
                    kill = next(kills, None)
                movement.frame(t, items)
            while kill is not None:
                movement.kill(kill)
                kill = next(kills, None)
            events.extend(recorded)
            if expected in {s * SECOND for s in (600, 900, 1500, 2400)} or expected == result["time_us"]:
                state = end_context
                while "bodies" not in state:
                    state = next(
                        state[k]
                        for k in ("carrion", "material", "enclosure", "group", "community", "world")
                        if k in state
                    )
                counts = Counter(e["kind"] for e in events)
                milestones.append(
                    {
                        "time_us": expected,
                        "alive": sum(bool(b["physical"]) for b in state["bodies"]),
                        "generation": max(b["generation"] for b in state["bodies"]),
                        "grain_stock": len(state["food"]),
                        "births": counts["birth"],
                        "predations": counts["body_engulfed"],
                        "scavenging": counts["carrion_meal"],
                    }
                )
    if expected != result["time_us"]:
        raise ValueError("wrong final time")
    roots = {i: family_roots(i, members) for i in members}
    nursing = defaultdict(lambda: {"contact_seconds": 0.0, "received": 0.0})
    growth_spent = 0.0
    ends = {}
    kills = defaultdict(list)
    counts = Counter(e["kind"] for e in events)
    kin = Counter()
    generations = defaultdict(Counter)
    for e in events:
        kind = e["kind"]
        i = e.get("individual")
        if kind == "body_growth":
            growth_spent += e["paid"]
        if kind == "nursing_contact":
            if (
                members[i]["parent"] != e["parent"]
                or not 0 <= e["age_us"] < 30 * SECOND
                or not 0 <= e["received"] <= e["duration_s"] + 1e-9
            ):
                raise ValueError("invalid nursing record")
            nursing[i]["contact_seconds"] += e["duration_s"]
            nursing[i]["received"] += e["received"]
        if kind in ("body_engulfed", "consciousness_dead", "body_age_limit"):
            ends.setdefault(i, e["time_us"])
        if kind == "body_engulfed":
            h = e["predator"]
            m = members[h]
            if e["method"] != "volume_contact" or not e["hunter_volume"] > e["prey_volume"] or e["surface_gap_m"] > 0:
                raise ValueError("invalid live predation")
            if not roots[h].isdisjoint(roots[i]):
                raise ValueError("protected live kin were eaten")
            kills[h].append(e["time_us"])
            relation = (
                "parent_child"
                if (m["parent"] == i or members[i]["parent"] == h)
                else ("siblings" if m["parent"] is not None and m["parent"] == members[i]["parent"] else "other")
            )
            kin[relation] += 1
            g = generations[m["generation"]]
            g["all_live_kills"] += 1
            if e["time_us"] < m["birth_us"] + 180 * SECOND:
                g["kills"] += 1
                g["nonkin_kills"] += int(relation == "other")
    if counts["body_engulfed"] != result["totals"]["predations"] or counts["birth"] != result["totals"]["births"]:
        raise ValueError("population totals differ")
    litters = Counter((e["parent"], e["time_us"]) for e in events if e["kind"] == "birth")
    first_child = {}
    for e in events:
        if e["kind"] == "birth":
            first_child.setdefault((e["parent"], e["time_us"]), e["individual"])
    if any(n != 3 for n in litters.values()) or any(m["physical"] != (i not in ends) for i, m in members.items()):
        raise ValueError("birth or survival histories differ")
    for i, m in members.items():
        g = generations[m["generation"]]
        g["individuals"] += 1
        g["hunters"] += int(bool(kills[i]))
        g["repeat_hunters"] += int(len(kills[i]) >= 2)
        g["alive_at_end"] += int(m["physical"])
        g["exposure_us"] += min(180 * SECOND, ends.get(i, expected) - m["birth_us"])

    def rate(gens, field):
        return ratio(
            sum(generations.get(g, {}).get(field, 0) for g in gens) * 6000 * SECOND,
            sum(generations.get(g, {}).get("exposure_us", 0) for g in gens),
        )

    early, late = rate((1, 2), "kills"), rate((3, 4, 5), "kills")
    return {
        "seconds": expected / SECOND,
        "extinct": result["extinct"],
        "alive": sum(m["physical"] for m in members.values()),
        "births": counts["birth"],
        "litters": len(litters),
        "grains": counts["nutrient_contact"],
        "carrion_meals": counts["carrion_meal"],
        "predations": counts["body_engulfed"],
        "predation_kin": dict(kin),
        "maximum_generation": max(generations),
        "deferred": result["totals"]["deferred_births"],
        "generations": dict(generations),
        "early_rate": early,
        "late_rate": late,
        "change": late - early if early is not None and late is not None else None,
        "nonkin_early": rate((1, 2), "nonkin_kills"),
        "nonkin_late": rate((3, 4, 5), "nonkin_kills"),
        "grain_energy": sum(e["energy"] for e in events if e["kind"] == "nutrient_contact"),
        "live_energy": sum(e["transferred"] for e in events if e["kind"] == "body_engulfed"),
        "carrion_energy": sum(e["received"] for e in events if e["kind"] == "carrion_meal"),
        "milestones": milestones,
        "reproduction": reproduction(
            {i: dict(m, radius=m["birth_radius"]) for i, m in members.items()}, ends, kills, expected, result["extinct"]
        ),
        "nursing_by_child": dict(nursing),
        "paid_growth": growth_spent,
        "birth_bills": [
            e["litter_bill"]
            for e in events
            if e["kind"] == "birth" and e["individual"] == first_child[e["parent"], e["time_us"]]
        ],
        "food_turns": meals.result(),
        "eligible_approaches": movement.approaches,
        "observed_pairs_5s": movement.exposed,
        "escape": movement.escape,
        "pursuit": movement.pursuit,
        "final_state_sha256": state_hash,
    }


def analyze(root):
    from paths import exclusive_json

    data = {}
    for i in range(len(SEEDS)):
        for arm in SUPPLIES:
            key = f"world-{i}-{arm}"
            cache = root / "analysis" / (key + ".json")
            if not cache.is_file():
                exclusive_json(cache, case_outcome(root / "cases" / key))
            data[key] = read(cache)
    low = [data[f"world-{i}-sparse"] for i in range(len(SEEDS))]
    diffs = []
    for i, c in enumerate(low):
        reference = data[f"world-{i}-reference"]["change"]
        diffs.append(None if c["change"] is None or reference is None else c["change"] - reference)
    outcomes = {
        "predation_over_generations": verdict([c["change"] for c in low]),
        "extra_change_under_lower_supply": verdict(diffs),
        "paired_change": diffs,
        "surviving_offspring": verdict([c["reproduction"]["adjusted_difference"] for c in low]),
    }
    for metric in ("food_turns", "pursuit", "escape"):
        per_world = [
            sum(
                (v[metric]["turns"] if metric == "food_turns" else len(v[metric]))
                for key, v in data.items()
                if key.startswith(f"world-{i}-")
            )
            for i in range(len(SEEDS))
        ]
        outcomes[metric] = {"per_world": per_world, "worlds_with_observations": sum(n > 0 for n in per_world)}
    return {"cases": data, "outcomes": outcomes}
