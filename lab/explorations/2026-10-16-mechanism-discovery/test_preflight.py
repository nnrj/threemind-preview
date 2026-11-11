"""Isolated preparation tests: no Core, subjects, database or network."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from lab.tools.mechanism_preflight import (
    COMPONENTS,
    audit_evidence,
    compare_witnesses,
    main,
    power_plan,
    safe_path,
    validate_program,
)

ROOT = Path(__file__).resolve().parents[3]
PROGRAM = ROOT / "lab/explorations/2026-10-16-mechanism-discovery/program.json"


@pytest.fixture
def tmp_path():
    # pytest's mode-0700 Windows temp directories are inaccessible to this
    # workstation sandbox. Use a unique ordinary workspace directory instead;
    # retain the tiny fixtures rather than touching another test run's files.
    path = ROOT / ".work/mechanism-preparation-20261016" / ("fixture-" + uuid4().hex)
    path.mkdir(parents=True)
    return path


def program():
    return json.loads(PROGRAM.read_text(encoding="utf-8"))


def witness():
    return {"schema": "threemind.observation-witness/1", "subject_id": "synthetic-only",
            "kernel": "synthetic/1", "canonicalization": "fixture/1", "boundary": "fixture",
            "simulated_time_us": 100, "input_sha256": "1" * 64, "event_order_sha256": "2" * 64,
            "components": {c: "3" * 64 for c in COMPONENTS}}


def test_preparation_never_means_run_permission(capsys):
    assert validate_program(program()) == []
    assert main(["validate", str(PROGRAM)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["execution_authorized"] is False
    assert len(result["pending_gates"]) == 7
    assert all(g == "pending" for p in result["pending_gates"].values() for g in p.values())


@pytest.mark.parametrize("change", ["permission", "pilot", "peeking", "cohorts", "gate", "criteria", "version", "pause"])
def test_protocol_rejects_scope_or_inference_changes(change):
    p = program()
    if change == "permission":
        p["execution_authorized"] = True
    elif change == "pilot":
        p["sampling"]["pilot_in_confirmation"] = True
    elif change == "peeking":
        p["sampling"]["outcome_based_extension"] = True
    elif change == "cohorts":
        p["packages"][1]["independent_delay_cohorts"] = False
    elif change == "gate":
        p["packages"][0]["gates"]["apparatus"] = "passed"
    elif change == "criteria":
        p["packages"][2]["criterion_version"] = "autonomy-criteria/post-hoc"
    elif change == "version":
        p["kernel"] = "threemind.continuous-memory/2"
    else:
        p["forbidden"].remove("new-subjects")
    assert validate_program(p)


def test_evidence_mismatch_missing_and_current_bytes_distinguished(tmp_path):
    p = tmp_path / "evidence.json"
    p.write_bytes(b"original")
    item = {"id": "old", "kind": "original_summary", "path": p.name,
            "basis": "synthetic fixture", "bytes": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
    manifest = {"schema": "threemind.mechanism-evidence/1", "files": [item]}
    assert audit_evidence(tmp_path, manifest)["ok"]
    p.write_bytes(b"changed!")
    assert audit_evidence(tmp_path, manifest)["files"][0]["status"] == "mismatch"
    p.unlink()
    assert audit_evidence(tmp_path, manifest)["files"][0]["status"] == "missing"
    assert not audit_evidence(tmp_path, manifest)["ok"]


@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/data", "a/../../escape", "a\\b"])
def test_no_unlisted_path_escape(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_duplicate_and_empty_evidence_not_accepted(tmp_path):
    assert not audit_evidence(tmp_path, {"schema": "threemind.mechanism-evidence/1", "files": []})["ok"]
    item = {"id": "same", "kind": "report", "path": "x", "basis": "fixture", "bytes": 1, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="duplicate"):
        audit_evidence(tmp_path, {"schema": "threemind.mechanism-evidence/1", "files": [item, item]})


@pytest.mark.parametrize("field", ["simulated_time_us", "event_order_sha256", "input_sha256", *sorted(COMPONENTS)])
def test_observation_witness_detects_hidden_changes(field):
    a, b = witness(), witness()
    assert compare_witnesses(a, b)["ok"]
    if field in COMPONENTS:
        b["components"][field] = "4" * 64
    else:
        b[field] = 101 if field == "simulated_time_us" else "4" * 64
    assert not compare_witnesses(a, b)["ok"]


def test_core_only_equality_cannot_pass_whole_system_comparison():
    a = witness()
    a["components"] = {"core": "3" * 64}
    assert not compare_witnesses(a, copy.deepcopy(a))["ok"]
    assert not compare_witnesses({}, {})["ok"]


def test_continuous_power_matches_noncentral_t_and_is_repeatable():
    from scipy.stats import nct, t
    result = power_plan(effect=0.5, family_size=3, replicates=10000)
    repeated = power_plan(effect=0.5, family_size=3, replicates=10000)
    assert result == repeated
    for row in result["rows"]:
        n = row["independent_units"]
        critical = t.ppf(1 - 0.05 / 6, n - 1)
        exact = nct.cdf(-critical, n - 1, 0.5 * n ** 0.5) + nct.sf(critical, n - 1, 0.5 * n ** 0.5)
        assert abs(row["power"] - exact) < 0.02
    assert result["execution_authorized"] is False


def test_multiplicity_and_underpowered_binary_scenario():
    single = power_plan(effect=0.5, family_size=1, replicates=2000)
    multiple = power_plan(effect=0.5, family_size=8, replicates=2000)
    assert single["selected_n"] <= multiple["selected_n"]
    binary = power_plan(kind="paired-binary", effect=0.1, family_size=4, replicates=10000,
                        baseline_success=0.5, discordance=0.3)
    assert binary["selected_n"] is None
    assert binary["decision"] == "redesign-measurement-before-confirmation"


@pytest.mark.parametrize("kwargs", [
    {"kind": "paired-binary", "effect": 0.1},
    {"kind": "paired-binary", "effect": 0.1, "baseline_success": 0.95, "discordance": 0.3},
    {"kind": "paired-binary", "effect": 0.1, "baseline_success": 0.5, "discordance": 0.05},
    {"effect": float("nan")}, {"effect": 0}, {"family_size": 0}, {"replicates": 0},
    {"baseline_success": 0.5}, {"seed": -1},
])
def test_invalid_power_assumptions_rejected(kwargs):
    with pytest.raises(ValueError):
        power_plan(**kwargs)


def test_no_run_command_or_subject_runtime_dependencies():
    import ast
    source = ROOT / "lab/tools/mechanism_preflight.py"
    tree = ast.parse(source.read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {x.name for n in ast.walk(tree) if isinstance(n, ast.Import) for x in n.names}
    assert all(not n.startswith(("threemind", "psycopg", "requests", "subprocess")) for n in imports)
    with pytest.raises(SystemExit) as exc:
        main(["run"])
    assert exc.value.code == 2


@pytest.mark.parametrize("value", [[], {"sampling": []}, {"packages": [None]}, {"packages": "M1"}])
def test_malformed_preparation_fails_closed(value):
    assert validate_program(value)


def test_malformed_witnesses_fail_closed():
    assert not compare_witnesses([], [])["ok"]
    a = witness()
    a["components"] = None
    assert not compare_witnesses(a, copy.deepcopy(a))["ok"]


def test_binary_power_matches_exact_unconditional_enumeration():
    import numpy as np
    from scipy.stats import binom

    result = power_plan(kind="paired-binary", effect=0.1, family_size=4,
                        baseline_success=0.5, discordance=0.3)
    for row in (result["rows"][0], result["rows"][-1]):
        n, exact = row["independent_units"], 0.0
        for discordant in range(n + 1):
            gain = np.arange(discordant + 1)
            reject = np.minimum(1, 2 * binom.cdf(np.minimum(gain, discordant - gain), discordant, 0.5)) <= 0.0125
            conditional = binom.pmf(gain, discordant, 2 / 3)[reject].sum()
            exact += binom.pmf(discordant, n, 0.3) * conditional
        assert abs(row["power"] - exact) < 0.012
