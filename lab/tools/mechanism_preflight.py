"""Offline preparation for mechanism studies. No subject, runtime or service access.

This module validates preparation records, streams hashes of selected evidence,
compares supplied whole-system witnesses, and simulates statistical power. Passing
these checks does not authorize execution or establish an experimental result.
All commands write JSON to stdout only; callers retain outputs in ignored storage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

COMPONENTS = {
    "core", "peripheral_weights", "optimizer", "random_state", "body",
    "mappings", "recent_activity", "actuators", "environment", "input_cursor",
}
GATES = {
    "evidence", "version_and_fields", "truth_isolation", "observation_invariance",
    "whole_system_restore", "apparatus", "pilot", "power", "frozen_confirmation",
    "resources", "execution_permission",
}
KINDS = {"report", "protocol", "original_summary", "source", "registry"}
FORBIDDEN = {"E69-resume", "new-subjects", "Core-changes", "service-or-schedule-changes",
             "cloud-purchases", "author-paper-edits"}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path: Path) -> tuple[int, str]:
    h, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
            size += len(block)
    return size, h.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    """Only explicit repository-relative files, including retained ignored data."""
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or ".." in p.parts or ":" in relative or "\\" in relative:
        raise ValueError(f"invalid relative evidence path: {relative}")
    target = root.joinpath(*p.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"evidence path escapes repository: {relative}")
    return target


def validate_program(program: dict) -> list[str]:
    errors = []
    if not isinstance(program, dict):
        return ["preparation must be an object"]
    if program.get("schema") != "threemind.mechanism-preparation/1":
        errors.append("unsupported preparation schema")
    if program.get("execution_authorized") is not False or program.get("status") != "preparation-only":
        errors.append("this preparation edition must not authorize execution")
    forbidden = program.get("forbidden", [])
    if not isinstance(forbidden, list) or not all(isinstance(v, str) for v in forbidden) or set(forbidden) != FORBIDDEN:
        errors.append("the explicit pause and implementation boundaries must be retained")
    if program.get("kernel") != "threemind.continuous-memory/5.1":
        errors.append("new-work kernel identity must remain /5.1")
    s = program.get("sampling", {})
    if not isinstance(s, dict):
        return errors + ["sampling must be an object"]
    expected = {"pilot_origins": 8, "confirmation_start": 48, "increment": 16,
                "maximum": 128, "target_power": 0.8, "alpha": 0.05,
                "continuous_effect": 0.5, "binary_difference": 0.1}
    if any(s.get(k) != v or type(s.get(k)) is bool for k, v in expected.items()):
        errors.append("sampling differs from the approved planning envelope")
    if s.get("pilot_in_confirmation") is not False or s.get("outcome_based_extension") is not False:
        errors.append("pilot reuse or outcome-based sample extension is forbidden")
    packages = program.get("packages", [])
    if not isinstance(packages, list) or any(not isinstance(p, dict) for p in packages):
        return errors + ["packages must be a list of objects"]
    if [p.get("id") for p in packages] != [f"M{i}" for i in range(1, 8)]:
        errors.append("expected ordered, unique packages M1 through M7")
    for p in packages:
        label = p.get("id", "?")
        for key in ("question", "backlog", "competitors", "primary_outcomes", "controls", "stop_conditions"):
            if not p.get(key):
                errors.append(f"{label}: missing {key}")
        backlog = p.get("backlog", [])
        if not isinstance(backlog, list) or any(
            not isinstance(x, str) or re.fullmatch(r"R\d{2}", x) is None for x in backlog
        ):
            errors.append(f"{label}: invalid stable backlog ID")
        if p.get("independent_unit") not in {"birth_origin", "world"}:
            errors.append(f"{label}: invalid independent unit")
        if p.get("status") != "protocol-prepared-not-run":
            errors.append(f"{label}: this edition contains no experimental results")
        if not isinstance(p.get("gates"), dict) or set(p["gates"]) != GATES:
            errors.append(f"{label}: incomplete launch gates")
        elif any(v != "pending" for v in p["gates"].values()):
            errors.append(f"{label}: launch gates need a separately evidenced later edition")
    by_id = {p.get("id"): p for p in packages}
    if by_id.get("M2", {}).get("delay_seconds") != [1, 30, 60, 300]:
        errors.append("M2: retention delays changed")
    if by_id.get("M2", {}).get("independent_delay_cohorts") is not True:
        errors.append("M2: early probes must not rehearse later-delay cohorts")
    if by_id.get("M3", {}).get("criterion_version") != "autonomy-criteria/1":
        errors.append("M3: original criterion version must be retained")
    return errors


def audit_evidence(root: Path, manifest: dict) -> dict:
    if manifest.get("schema") != "threemind.mechanism-evidence/1":
        raise ValueError("unsupported evidence schema")
    rows, seen = [], set()
    for item in manifest["files"]:
        key = item["id"]
        if key in seen:
            raise ValueError(f"duplicate evidence ID: {key}")
        seen.add(key)
        if item["kind"] not in KINDS or not HEX.fullmatch(item["sha256"]):
            raise ValueError(f"invalid evidence declaration: {key}")
        if type(item["bytes"]) is not int or item["bytes"] < 0:
            raise ValueError(f"invalid evidence size: {key}")
        path = safe_path(root, item["path"])
        row = {"id": key, "kind": item["kind"], "path": item["path"], "basis": item["basis"]}
        try:
            size, actual = digest(path)
            row.update(bytes=size, sha256=actual,
                       status="match" if (size, actual) == (item["bytes"], item["sha256"]) else "mismatch")
        except FileNotFoundError:
            row["status"] = "missing"
        except OSError as exc:
            row.update(status="unreadable", error=type(exc).__name__)
        rows.append(row)
    return {"schema": "threemind.mechanism-evidence-audit/1", "ok": bool(rows) and
            all(r["status"] == "match" for r in rows), "files": rows,
            "scope": "selected file bytes only; no database readback, full-archive audit, or result recomputation",
            "execution_authorized": False}


def compare_witnesses(a: dict, b: dict) -> dict:
    """Compare caller-supplied witnesses; never load or advance a saved subject.

    Equal hashes are meaningful only when the caller generated complete canonical
    states at the same declared boundary. This tool cannot establish that fact.
    """
    errors = []
    if not isinstance(a, dict) or not isinstance(b, dict):
        return {"ok": False, "errors": ["witnesses must be objects"], "execution_authorized": False}
    for label, witness in (("a", a), ("b", b)):
        if witness.get("schema") != "threemind.observation-witness/1":
            errors.append(f"{label}: unsupported witness schema")
        components = witness.get("components", {})
        if not isinstance(components, dict):
            errors.append(f"{label}: components must be an object")
            components = {}
        if set(components) != COMPONENTS:
            errors.append(f"{label}: missing or undeclared whole-system component")
        for name, h in components.items():
            if not isinstance(h, str) or not HEX.fullmatch(h):
                errors.append(f"{label}: invalid digest for {name}")
        for name in ("input_sha256", "event_order_sha256"):
            if not isinstance(witness.get(name), str) or not HEX.fullmatch(witness[name]):
                errors.append(f"{label}: missing {name}")
        if type(witness.get("simulated_time_us")) is not int or witness.get("simulated_time_us", -1) < 0:
            errors.append(f"{label}: invalid simulated time")
        for name in ("subject_id", "kernel", "canonicalization", "boundary"):
            if not isinstance(witness.get(name), str) or not witness[name].strip():
                errors.append(f"{label}: missing {name}")
    keys = ("subject_id", "kernel", "canonicalization", "boundary", "simulated_time_us",
            "input_sha256", "event_order_sha256", "components")
    errors += [f"different {key}" for key in keys if a.get(key) != b.get(key)]
    return {"ok": not errors, "errors": errors, "execution_authorized": False,
            "scope": "supplied witness comparison, not a live observation-invariance experiment"}


def wilson(successes: int, count: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = successes / count
    center = (p + z * z / (2 * count)) / (1 + z * z / count)
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    return center - radius, center + radius


def power_plan(*, kind="continuous", effect=0.5, family_size=1, replicates=10000,
               seed=20261016, baseline_success=None, discordance=None) -> dict:
    """Planning simulation over independent origin-level paired outcomes.

    Continuous: normal paired differences, variance=1, two-sided one-sample t.
    Binary: ONE paired Bernoulli outcome per origin, exact McNemar test.
    Repeated questions and descendants cannot be passed as independent trials.
    Bonferroni alpha is conservative for the planned Holm confirmation family.
    No ThreeMind execution, pilot observations, or experimental results occur.
    """
    import numpy as np
    from scipy.stats import binom, t

    if kind not in {"continuous", "paired-binary"}:
        raise ValueError("unsupported outcome model")
    if not math.isfinite(effect) or not 0 < effect <= 1:
        raise ValueError("effect must be finite in (0, 1]")
    if type(family_size) is not int or not 1 <= family_size <= 100:
        raise ValueError("family size must be an integer in [1, 100]")
    if type(replicates) is not int or not 2000 <= replicates <= 100000:
        raise ValueError("planning replicates must be in [2000, 100000]")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    probabilities = None
    if kind == "paired-binary":
        if baseline_success is None or discordance is None:
            raise ValueError("binary planning requires baseline success and discordance assumptions")
        p, q = baseline_success, discordance
        if not all(math.isfinite(x) for x in (p, q)) or not 0 <= p <= 1 - effect:
            raise ValueError("invalid binary baseline")
        if not effect <= q <= min(2 * p + effect, 2 - 2 * p - effect):
            raise ValueError("infeasible binary discordance")
        gain, loss = (q + effect) / 2, (q - effect) / 2
        probabilities = [gain, loss, 1 - q]
    elif baseline_success is not None or discordance is not None:
        raise ValueError("binary assumptions are not used by the continuous model")
    alpha = 0.05 / family_size
    rows = []
    # Independent seeded streams for each N; memory stays below 512 x 128 floats.
    for n in range(48, 129, 16):
        rng, passed = np.random.default_rng(np.random.SeedSequence([seed, n])), 0
        for start in range(0, replicates, 512):
            count = min(512, replicates - start)
            if kind == "continuous":
                sample = rng.normal(effect, 1, (count, n))
                statistic = sample.mean(axis=1) / (sample.std(axis=1, ddof=1) / math.sqrt(n))
                passed += int(np.sum(abs(statistic) > t.ppf(1 - alpha / 2, n - 1)))
            else:
                counts = rng.multinomial(n, probabilities, size=count)
                pairs = counts[:, 0] + counts[:, 1]
                pvalues = np.minimum(1, 2 * binom.cdf(np.minimum(counts[:, 0], counts[:, 1]), pairs, 0.5))
                passed += int(np.sum(pvalues <= alpha))
        low, high = wilson(passed, replicates)
        rows.append({"independent_units": n, "power": passed / replicates,
                     "monte_carlo_95_interval": [low, high], "meets_planning_target": low >= 0.8})
    selected = next((r["independent_units"] for r in rows if r["meets_planning_target"]), None)
    return {"schema": "threemind.mechanism-power/1", "kind": kind, "effect": effect,
            "family_size": family_size, "per_comparison_alpha": alpha, "replicates": replicates,
            "seed": seed, "baseline_success": baseline_success, "discordance": discordance,
            "rows": rows, "selected_n": selected,
            "decision": "conditional-planning-estimate" if selected else "redesign-measurement-before-confirmation",
            "scope": "assumed independent paired outcomes; not pilot-fitted or final sample authorization",
            "execution_authorized": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate")
    p.add_argument("program", type=Path)
    p = sub.add_parser("audit")
    p.add_argument("manifest", type=Path)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    p = sub.add_parser("compare-witnesses")
    p.add_argument("first", type=Path)
    p.add_argument("second", type=Path)
    p = sub.add_parser("power")
    p.add_argument("--kind", choices=["continuous", "paired-binary"], default="continuous")
    p.add_argument("--effect", type=float, default=0.5)
    p.add_argument("--family-size", type=int, default=1)
    p.add_argument("--replicates", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20261016)
    p.add_argument("--baseline-success", type=float)
    p.add_argument("--discordance", type=float)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            program = read_json(args.program)
            errors = validate_program(program)
            result = {"ok": not errors, "errors": errors, "execution_authorized": False,
                      "pending_gates": {} if errors else {p["id"]: p["gates"] for p in program["packages"]},
                      "scope": "preparation-schema check; no claim of launch readiness"}
        elif args.command == "audit":
            result = audit_evidence(args.repo, read_json(args.manifest))
        elif args.command == "compare-witnesses":
            result = compare_witnesses(read_json(args.first), read_json(args.second))
        else:
            result = power_plan(**{k: v for k, v in vars(args).items() if k != "command"})
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.get("ok", True) else 1
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "execution_authorized": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
