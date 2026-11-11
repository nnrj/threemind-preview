"""Bounded synthetic engineering profile; never loads a research individual.

Prepare an ignored COPY of Rust sources, add feature-gated instrumentation there,
and build/run it separately. No extension is installed and no Core source edited.
Raw output belongs under .work, not in Git. Timed builds must be compared with
uninstrumented builds; instrumentation overhead is not production latency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    "local.rs": ["advance_impl", "receive", "receive_batch", "associate", "touch", "emit", "settle_node", "node_value", "settle_edge", "edge_value", "discrete_edge_state", "node_timers", "edge_timer", "timer", "pulse", "outgoing_keys", "incident_keys", "expiry", "event", "features", "maintenance"],
    "retention.rs": ["prepare_edge", "edge_value", "settle_node", "node_value", "schedule_edge", "edge_changed", "emitted", "timer", "touch", "schedule_node", "prune", "grow", "decay", "crossing"],
    "restoration.rs": ["relax", "touch", "update_touched", "stimulate", "adapt_candidate", "generate_inhibition", "prune", "lifecycle"],
    "continuous.rs": ["emit_continuous", "receive", "release_fraction", "effective_weight", "record_emission", "prune_operator_state"],
    "lib.rs": ["advance_impl", "associate", "homeostasis", "event"],
}


def prepare(work: Path):
    work.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for crate in ("threemind-core", "threemind-causal-legacy", "threemind-causal8-legacy"):
        source = ROOT / "crates" / crate
        shutil.copytree(source, work / "crates" / crate)
        for path in source.rglob("*"):
            if path.is_file():
                hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (work / "Cargo.toml").write_text('''[workspace]
members = ["crates/threemind-core", "crates/threemind-causal-legacy", "crates/threemind-causal8-legacy", "driver"]
resolver = "2"
[workspace.package]
version = "2.0.0"
edition = "2021"
[profile.release]
lto = "thin"
codegen-units = 1
''', encoding="utf-8")
    shutil.copy2(ROOT / "Cargo.lock", work / "Cargo.lock")
    core = work / "crates/threemind-core"
    with (core / "Cargo.toml").open("a", encoding="utf-8") as f:
        f.write('\n[features]\nkernel-probe = []\n')
    names = []
    for name, functions in FUNCTIONS.items():
        path = core / "src" / name
        # /5.1 shares transition source with the historical wrapper. Retain
        # stable probe names so earlier profiles remain directly comparable.
        if name == "local.rs" and (core / "src/local_shared.rs").exists():
            path = core / "src/local_shared.rs"
        source = path.read_text(encoding="utf-8")
        for function in functions:
            pattern = re.compile(r"(\bfn " + function + r"\s*\([^{}]*?\)[^{}]*?\{)", re.DOTALL)
            matches = list(pattern.finditer(source))
            if len(matches) != 1:
                raise ValueError((name, function, len(matches)))
            key = name.removesuffix(".rs") + "::" + function
            index = len(names)
            names.append(key)
            source = pattern.sub(lambda m, index=index: m[0] + f'\n        #[cfg(feature="kernel-probe")] let _probe_scope = crate::probe::enter({index});', source, count=1)
        if name == "local.rs":
            marker = "for &(a, av, ai) in &contacts {"
            assert source.count(marker) == 1
            source = source.replace(marker, '#[cfg(feature="kernel-probe")] crate::probe::add_pairs(contacts.len());\n        ' + marker)
        path.write_text(source, encoding="utf-8")
    with (core / "src/lib.rs").open("a", encoding="utf-8") as f:
        f.write('\npub mod probe;\n')
    names_text = ",".join(json.dumps(n) for n in names)
    probe = (ROOT / "tools/kernel_locality_probe.rs").read_text(encoding="utf-8")
    (core / "src/probe.rs").write_text(probe.replace("__FUNCTION_NAMES__", names_text), encoding="utf-8")
    driver = work / "driver/src"
    driver.mkdir(parents=True)
    (driver.parent / "Cargo.toml").write_text('''[package]
name = "kernel-locality-probe"
version = "0.1.0"
edition = "2021"
[dependencies]
threemind-core = { path = "../crates/threemind-core" }
serde_json = "1"
[features]
kernel-probe = ["threemind-core/kernel-probe"]
''', encoding="utf-8")
    shutil.copy2(ROOT / "tools/kernel_locality_driver.rs", driver / "main.rs")
    from threemind_kernels.local import LocalConfig
    from threemind_kernels.local5 import Local5Config
    from threemind_kernels.local51 import Local51Config
    from threemind_kernels.novelty import NoveltyConfig
    from threemind_kernels.retention31 import Retention31Config
    configs = {"2": NoveltyConfig(seed=223).to_dict(), "3.1": Retention31Config(seed=223).to_dict(), "4-h": LocalConfig(seed=223).to_dict(), "4-s": LocalConfig(seed=223, consolidation_mode="legacy-stability").to_dict()}
    configs.update({"5-h": Local5Config(seed=223).to_dict(),
                    "5-s": Local5Config(seed=223, consolidation_mode="legacy-stability").to_dict(),
                    "5-no-h": Local5Config(seed=223, consolidation_mode="legacy-stability", node_retention_mode="manual").to_dict()})
    configs.update({"5.1-h": Local51Config(seed=223).to_dict(),
                    "5.1-s": Local51Config(seed=223, consolidation_mode="legacy-stability").to_dict()})
    (work / "configs.json").write_text(json.dumps(configs), encoding="utf-8")
    (work / "source-hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps({"work": str(work), "source_files": len(hashes), "instrumented_functions": len(names)}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "candidate", "build", "run", "summarize"])
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--profile", action="store_true")
    p.add_argument("--candidate", action="store_true")
    p.add_argument("--channels", type=int, default=32)
    p.add_argument("--seconds", type=int, default=2)
    p.add_argument("--arm", choices=["2", "3.1", "4-h", "4-s", "5-h", "5-s", "5-no-h", "5.1-h", "5.1-s"], default="4-h")
    p.add_argument("--pattern", choices=["dense", "pairs"], default="dense")
    p.add_argument("--label", default="r1")
    args = p.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to(ROOT / ".work"):
        raise ValueError("Engineering work directory must be under repo .work")
    if args.action == "prepare":
        prepare(work)
    elif args.action == "summarize":
        def read(name):
            return json.loads((work / name).read_text(encoding="utf-8"))
        arms = ["2", "3.1", "4-h", "4-s"]
        profile_checks = []
        for n in [16, 32, 64]:
            for arm in arms:
                base = read(f"{arm}-{n}-2-r1-baseline.exe.json")
                prof = read(f"{arm}-{n}-2-r1-profile.exe.json")
                assert base["state_hash"] == prof["state_hash"]
                profile_checks.append({"arm": arm, "channels": n, "state_hash": base["state_hash"], "baseline_s": base["advance_s"], "profile": prof["profile"]})
        repeats = {}
        for arm in arms:
            base = [read(f"{arm}-64-2-r{r}-baseline.exe.json") for r in [2, 3, 4]]
            cand = [read(f"{arm}-64-2-r{r}-candidate.exe.json") for r in [2, 3, 4]]
            assert len({r["state_hash"] for r in base + cand}) == 1
            b = [r["advance_s"] for r in base]
            c = [r["advance_s"] for r in cand]
            repeats[arm] = {"baseline_s": b, "candidate_s": c, "baseline_median": statistics.median(b), "candidate_median": statistics.median(c), "paired_reduction_percent": [100*(x-y)/x for x,y in zip(b,c)], "state_hash": base[0]["state_hash"]}
        named = {"config": work / "configs.json", "original_sources": work / "source-hashes.json", "candidate_changes": work / "candidate-changes.json", "lock": work / "Cargo.lock"}
        named.update({s: work / (s + ".exe") for s in ["baseline", "profile", "candidate"]})
        named.update({s: ROOT / "tools" / s for s in ["profile_kernel_locality.py", "kernel_locality_driver.rs", "kernel_locality_probe.rs", "audit_kernel_stage_costs.py"]})
        provenance = {k: {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in named.items()}
        summary = {"schema": "threemind.kernel-locality-engineering/1", "scope": "Fresh synthetic engineering fixtures only; no research restoration or installed-kernel modification", "compiler": subprocess.check_output(["rustc", "-Vv"], text=True), "provenance": provenance, "profile_checks": profile_checks, "repeats_64_channels": repeats, "caveats": ["Final full-state equality on these fixtures, not all intermediate formal trajectories.", "Instrumentation counts are exact for covered calls; timing includes probe overhead and is not production CPU attribution.", "Shared workstation wall time; repeated pairs alternate execution order; no promise of formal-course speedup.", "Copy-only candidate retains all scientific rules; production integration and full compatibility checks remain unperformed."]}
        with (work / "engineering-summary.json").open("x", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(repeats, ensure_ascii=False))
    elif args.action == "candidate":
        if (work / "crates/threemind-core/src/local_shared.rs").exists():
            raise ValueError("This historical candidate applies only to the pre-/5.1 source layout; use its frozen source copy")
        # Only an isolated-copy proposal: unchanged deadline and short-circuit
        # condition ordering. Never apply these edits to the installed engine.
        changes = {
            "retention.rs": [('fn timer(&mut self, k: TimerKey, time: Option<u128>) {', 'fn timer(&mut self, k: TimerKey, time: Option<u128>) {\n        if self.timers.get(&k).copied() == time { return; }')],
            "local.rs": [('fn timer(&mut self, key: Timer, time: Option<u128>) {', 'fn timer(&mut self, key: Timer, time: Option<u128>) {\n        if self.deadlines.get(&key).copied() == time { return; }')],
            "continuous.rs": [('if !traversed.contains(&(e.source, e.target))\n                    && self.retention.as_ref().is_none_or(|op| !op.p.adaptive())', 'if self.retention.as_ref().is_none_or(|op| !op.p.adaptive())\n                    && !traversed.contains(&(e.source, e.target))')],
        }
        marker = work / "candidate-changes.json"
        if marker.exists():
            raise ValueError("Candidate changes already applied")
        for name, replacements in changes.items():
            path = work / "crates/threemind-core/src" / name
            content = path.read_text(encoding="utf-8")
            for before, after in replacements:
                if content.count(before) != 1:
                    raise ValueError((name, "unexpected source"))
                content = content.replace(before, after)
            path.write_text(content, encoding="utf-8")
        marker.write_text(json.dumps(changes, indent=2), encoding="utf-8")
    elif args.action == "build":
        if any(work.glob("memory5-perf-*.json")):
            raise ValueError("Use separately named builds for memory5 performance candidates; do not overwrite baseline/profile witnesses")
        if args.candidate != (work / "candidate-changes.json").exists():
            raise ValueError("Build label must match whether copy-only candidates were applied")
        if args.profile and args.candidate:
            raise ValueError("Candidate throughput is measured without instrumentation")
        command = ["cargo", "build", "--offline", "--release", "-p", "kernel-locality-probe"]
        if args.profile:
            command += ["--features", "kernel-probe"]
        subprocess.run(command, cwd=work, check=True, timeout=240)
        shutil.copy2(work / "target/release/kernel-locality-probe.exe", work / ("candidate.exe" if args.candidate else "profile.exe" if args.profile else "baseline.exe"))
    else:
        if not 1 <= args.channels <= 1024 or not 1 <= args.seconds <= 100:
            raise ValueError("Keep this synthetic engineering probe bounded")
        if args.pattern == "pairs" and args.channels % 2:
            raise ValueError("pairs requires even channels")
        binary = "candidate.exe" if args.candidate else "profile.exe" if args.profile else "baseline.exe"
        result = subprocess.run([str(work / binary), str(work / "configs.json"), args.arm, str(args.channels), str(args.seconds), args.pattern], text=True, encoding="utf-8", capture_output=True, check=True, timeout=120)
        data = json.loads(result.stdout)
        data.update(profiled=args.profile, candidate=args.candidate, scope="Synthetic engineering fixture, not research subject or shape/color score", source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
        suffix = '' if args.pattern == 'dense' else f'-{args.pattern}'
        output = work / f'{args.arm}-{args.channels}-{args.seconds}-{args.label}{suffix}-{binary}.json'
        with output.open("x", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(json.dumps({"output": str(output), "advance_s": data["advance_s"], "hash": data["state_hash"], "nodes": data["metrics"]["nodes"], "edges": data["metrics"]["edges"]}))


if __name__ == "__main__":
    main()
