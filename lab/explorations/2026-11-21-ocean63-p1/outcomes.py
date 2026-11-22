"""Independent event, generation and movement analysis of sealed P1 worlds."""

from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.ipc as ipc

from paths import SECOND, SEEDS, SUPPLIES, read
from execution import encoded
from turns import EncounterTurns, MealTurns


def ratio(a, b):
    return a / b if b else None


def reproduction(members, ends, kills, end, extinct):
    children = defaultdict(list)
    for i, m in members.items():
        if m["parent"] is not None:
            children[m["parent"]].append(i)
    rows = []
    excluded = Counter()
    for i, m in members.items():
        birth = m["birth_us"]
        if not m["generation"]:
            continue
        if ends.get(i, float("inf")) < birth + 60 * SECOND:
            excluded["died_before_60"] += 1
            continue
        if birth + 240 * SECOND > end and not extinct:
            excluded["short_followup"] += 1
            continue
        early = any(birth <= t < birth + 60 * SECOND for t in kills.get(i, []))
        young = [j for j in children[i] if birth + 60 * SECOND <= members[j]["birth_us"] < birth + 180 * SECOND]
        survived = sum(ends.get(j, float("inf")) >= members[j]["birth_us"] + 60 * SECOND for j in young)
        census = birth + 240 * SECOND

        def living(j):
            return members[j]["birth_us"] <= census and ends.get(j, float("inf")) > census

        all_desc = []
        stack = list(children[i])
        while stack:
            child = stack.pop()
            if members[child]["birth_us"] <= census:
                all_desc.append(child)
                stack.extend(children[child])
        band = sum(m["radius"] / 0.008 >= limit for limit in (0.85, 1.0, 1.15))
        rows.append(
            dict(
                individual=i,
                generation=m["generation"],
                size_band=band,
                early_hunter=early,
                births_in_window=len(young),
                children_survived_to_60=survived,
                living_direct_at_240=sum(living(j) for j in children[i]),
                living_descendants_at_240=sum(living(j) for j in all_desc),
            )
        )
    groups = defaultdict(list)
    strata = defaultdict(lambda: defaultdict(list))
    for row in rows:
        role = "hunter" if row["early_hunter"] else "other"
        groups[role].append(row)
        strata[row["generation"], row["size_band"]][role].append(row["children_survived_to_60"])
    summary = {}
    for role in ("hunter", "other"):
        entries = groups[role]
        summary[role] = dict(
            eligible=len(entries),
            surviving_children=sum(r["children_survived_to_60"] for r in entries),
            born=sum(r["births_in_window"] for r in entries),
            living_descendants_at_240=sum(r["living_descendants_at_240"] for r in entries),
        )
        summary[role]["mean"] = ratio(summary[role]["surviving_children"], len(entries))
    matched = []
    for (gen, size), s in sorted(strata.items()):
        h, c = s["hunter"], s["other"]
        if h and c:
            matched.append(
                dict(
                    generation=gen,
                    size_band=size,
                    hunters=len(h),
                    others=len(c),
                    weight=min(len(h), len(c)),
                    difference=sum(h) / len(h) - sum(c) / len(c),
                )
            )
    weight = sum(s["weight"] for s in matched)
    diff = ratio(sum(s["weight"] * s["difference"] for s in matched), weight)
    a, b = summary["hunter"]["mean"], summary["other"]["mean"]
    return dict(
        groups=summary,
        excluded=dict(excluded),
        matched_strata=matched,
        adjusted_difference=diff,
        crude_difference=a - b if a is not None and b is not None else None,
        individuals=rows,
    )


def case_outcome(case):
    result = read(case / "result.json")
    members = {m["id"]: m for m in result["members"]}
    with ZipFile(case / "initial.zip") as z:
        initial = json.loads(z.read("world.json"))
    state_hash = hashlib.sha256(encoded(initial["context"])).hexdigest()
    meals = MealTurns()
    movement = EncounterTurns(initial["protocol"]["side_m"], members)
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
                    dict(
                        time_us=expected,
                        alive=sum(bool(b["physical"]) for b in state["bodies"]),
                        generation=max(b["generation"] for b in state["bodies"]),
                        grain_stock=len(state["food"]),
                        births=counts["birth"],
                        predations=counts["body_engulfed"],
                        scavenging=counts["carrion_meal"],
                    )
                )
    if expected != result["time_us"]:
        raise ValueError("wrong final time")
    ends = {}
    kills = defaultdict(list)
    counts = Counter(e["kind"] for e in events)
    kin = Counter()
    generations = defaultdict(Counter)
    for e in events:
        kind = e["kind"]
        i = e.get("individual")
        if kind in ("body_engulfed", "consciousness_dead", "body_age_limit"):
            ends.setdefault(i, e["time_us"])
        if kind == "body_engulfed":
            h = e["predator"]
            m = members[h]
            if e["method"] != "volume_contact" or not e["hunter_volume"] > e["prey_volume"] or e["surface_gap_m"] > 0:
                raise ValueError("invalid live predation")
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
    if any(n != 2 for n in litters.values()) or any(m["physical"] != (i not in ends) for i, m in members.items()):
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
    return dict(
        seconds=expected / SECOND,
        extinct=result["extinct"],
        alive=sum(m["physical"] for m in members.values()),
        births=counts["birth"],
        litters=len(litters),
        grains=counts["nutrient_contact"],
        carrion_meals=counts["carrion_meal"],
        predations=counts["body_engulfed"],
        predation_kin=dict(kin),
        maximum_generation=max(generations),
        deferred=result["totals"]["deferred_births"],
        generations=dict(generations),
        early_rate=early,
        late_rate=late,
        change=late - early if early is not None and late is not None else None,
        nonkin_early=rate((1, 2), "nonkin_kills"),
        nonkin_late=rate((3, 4, 5), "nonkin_kills"),
        grain_energy=sum(e["energy"] for e in events if e["kind"] == "nutrient_contact"),
        live_energy=sum(e["transferred"] for e in events if e["kind"] == "body_engulfed"),
        carrion_energy=sum(e["received"] for e in events if e["kind"] == "carrion_meal"),
        milestones=milestones,
        reproduction=reproduction(members, ends, kills, expected, result["extinct"]),
        food_turns=meals.result(),
        eligible_approaches=movement.approaches,
        observed_pairs_5s=movement.exposed,
        escape=movement.escape,
        pursuit=movement.pursuit,
        final_state_sha256=state_hash,
    )


def verdict(values):
    if any(v is None for v in values):
        return "insufficient"
    return "supported" if all(v > 0 for v in values) else "not_met"


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
    outcomes = dict(
        predation_over_generations=verdict([c["change"] for c in low]),
        extra_change_under_lower_supply=verdict(diffs),
        paired_change=diffs,
        surviving_offspring=verdict([c["reproduction"]["adjusted_difference"] for c in low]),
    )
    for metric in ("food_turns", "pursuit", "escape"):
        per_world = [
            sum(
                (v[metric]["turns"] if metric == "food_turns" else len(v[metric]))
                for key, v in data.items()
                if key.startswith(f"world-{i}-")
            )
            for i in range(len(SEEDS))
        ]
        outcomes[metric] = dict(per_world=per_world, worlds_with_observations=sum(n > 0 for n in per_world))
    return dict(cases=data, outcomes=outcomes)
