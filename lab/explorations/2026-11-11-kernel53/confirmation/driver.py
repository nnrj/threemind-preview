"""Serial R47b confirmation host using the existing recorder, API and complete-boundary guard."""

import argparse
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NATIVE = ROOT / ".work/native53-release"
sys.path[:0] = [str(NATIVE), str(ROOT), str(ROOT / "lab/explorations/2026-10-16-mechanism-discovery")]
import httpx
import psutil
import pilot_m2 as base
sys.path.insert(0, str(HERE.parent))
from assay import Assay, KERNEL_ID
from spec import cases

WORK = Path("E:/ThreeMindData/experiments/2026-11-11-kernel53/confirmation-v1")
NS = UUID("1dc5fba0-96a3-54f3-a941-ff578893ea52")
RESOURCE = "kernel53-retention-confirmation-20261111-v1"
POLICY = dict(
    reserve_gib=dict(commit=5, ram=4, system_disk=5, data_disk=25),
    private_bytes=2**30,
    originals_bytes=3 * 2**30,
    wall_seconds=7200,
    startup_commit_bytes=8 * 2**30,
    poll_seconds=1,
)


def ident(key):
    return uuid5(NS, key)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    return base.original(path, value, compressed=str(path).endswith(".gz"))


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def implementation():
    native = importlib.import_module("_threemind_native")
    binary = Path(native.__file__).resolve()
    if binary.parent != NATIVE or not hasattr(native, "NativeLocal53"):
        raise RuntimeError("isolated /5.3 release module required")
    result = base.capture_implementation("reference")
    result.update(backend="native", native_binary_sha256=sha(binary), native_binary_path=str(binary))
    # Add the new compiled default contract, omitted by the historical collector.
    path = ROOT / "crates/threemind-core/src/local53-defaults.json"
    result["source_files"][path.relative_to(ROOT).as_posix()] = sha(path)
    return result


def manifest():
    paths = [
        HERE / name
        for name in ("spec.py", "driver.py", "analyze.py", "audit.py", "test_assay.py", "power.py", "power.json", "protocol.zh.md", "protocol.en.md")
    ]
    paths += [HERE.parent / n for n in ("assay.py", "analyze.py", "audit.py", "study.py")]
    paths += [
        ROOT / rel
        for rel in (
            "lab/tools/study_lock.py",
            "lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py",
            "lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py",
        )
    ]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def connection():
    base.load_env()
    db = urlsplit(os.environ.get("THREEMIND_DATABASE_URL", ""))
    if db.hostname not in ("localhost", "127.0.0.1", "::1") or db.port != 5433:
        raise RuntimeError("local research database required")
    return base.OperationsClient(
        url="http://127.0.0.1:8877",
        username=os.environ.get("THREEMIND_API_USERNAME"),
        password=os.environ.get("THREEMIND_API_PASSWORD"),
        token=os.environ.get("THREEMIND_API_TOKEN"),
        transport=httpx.HTTPTransport(trust_env=False),
        reuse_session=False,
        require_auth=True,
        source="ai",
    )


def verify(path):
    if path.exists():
        raise ValueError("preserve previous verification; select a fresh path")
    path.mkdir(parents=True)
    code = (
        "import sys; sys.path[:0]="
        + repr([str(NATIVE), str(ROOT / ".work")])
        + "; import pytest; raise SystemExit(pytest.main("
        + repr(
            [
                str(ROOT / "tests_v2/test_local53.py"),
                str(HERE / "test_assay.py"),
                "-q",
                "--tb=short",
                "--maxfail=1",
                "--noconftest",
                "-p",
                "no:tmpdir",
                "-p",
                "pytest53_fixtures",
            ]
        )
        + "))"
    )
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    (path / "test-output.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    save(
        path / "verified.json",
        dict(
            passed=result.returncode == 0,
            returncode=result.returncode,
            manifest=manifest(),
            implementation=implementation(),
            cases_sha256=base.digest(cases()),
            test_output_sha256=sha(path / "test-output.txt"),
            scientific_sources_used=False,
        ),
    )
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError("apparatus verification failed")


def prepare(work, instrument):
    receipt = load(instrument / "verified.json")
    assert receipt["passed"] and receipt["manifest"] == manifest() and receipt["implementation"] == implementation()
    assert receipt["cases_sha256"] == base.digest(cases())
    work.mkdir(parents=True, exist_ok=True)
    with base.worker_lock(work), connection() as client:
        if (work / "platform.json").exists():
            raise RuntimeError("already prepared or partial registration; reconcile rather than repeat")
        resource = base.resource_check(work)
        assert resource["available_bytes"]["commit"] >= POLICY["startup_commit_bytes"]
        assert resource["available_bytes"]["data_disk"] >= 34 * 2**30
        title = "2026-11-11 ThreeMind · 5.3单年龄衰减保持确认 R47b"
        candidates = [p for p in client.call("projects.list", {}) if p["name"] == title]
        if len(candidates) > 1:
            raise RuntimeError("ambiguous project")
        project = candidates[0] if candidates else client.request("POST", "/api/v2/projects", body=dict(name=title))
        save(work / "platform.json", dict(project_id=project["id"], resource_id=RESOURCE))
        recorder = base.ResearchRecorder(work, project["id"], client=client)
        recorder.register(
            dict(
                source_key="kernel53:retention-confirmation:20261111:v1",
                title=title,
                classification="formal",
                execution_status="running",
                executor="ai",
                kernels=[KERNEL_ID],
                protocol=(HERE / "protocol.zh.md").read_text("utf-8"),
                protocol_version=base.digest(manifest()),
                required_roles=["protocol", "report", "note"],
                metadata=dict(
                    independent_origins=48,
                    sequences=len(cases()),
                    work=str(work),
                    policy=POLICY,
                    authorization="User explicitly approved implementing ThreeMind 5.3 plan",
                ),
            ),
            request_id=ident("register"),
        )
        recorder.synchronize(strict=True)
        client.request(
            "POST",
            "/api/v2/storage/resources",
            body=dict(
                resource_id=RESOURCE,
                target_id="managed-research-experiments",
                relative_path="2026-11-11-kernel53/confirmation-v1",
                registered_work_path=str(work),
                writer_mode="cooperative",
                expected_revision=0,
            ),
            headers={"X-ThreeMind-Request-ID": str(ident("resource"))},
        )
        client.request(
            "POST",
            "/api/v2/storage/record-evidence-grants",
            body=dict(project_id=project["id"], resource_id=RESOURCE),
            headers={"X-ThreeMind-Request-ID": str(ident("grant"))},
        )
        save(work / "runner-manifest.json", manifest())
        save(work / "implementation.json", implementation())
        save(work / "policy.json", POLICY)
        save(work / "cases.json", cases())
        save(work / "instrument/verified.json", receipt)
        for rel in set(manifest()) | set(implementation()["source_files"]):
            recorder.save_original("frozen/" + rel, (ROOT / rel).read_bytes())
        recorder.save_original(
            "frozen-native/_threemind_native.pyd", Path(implementation()["native_binary_path"]).read_bytes()
        )
        for lang in ("zh", "en"):
            recorder.text(
                dict(
                    request_id=str(ident("protocol-" + lang)),
                    identity=str(ident("protocol-doc-" + lang)),
                    expected_revision=0,
                    kind="protocol",
                    title="R47b single-age retention confirmation " + lang,
                    markdown=(HERE / f"protocol.{lang}.md").read_text("utf-8"),
                )
            )
        recorder.synchronize(strict=True)
        readback = []
        for lang in ("zh", "en"):
            doc = client.request(
                "GET", f"/api/v2/projects/{project['id']}/research-documents/{ident('protocol-doc-' + lang)}"
            )
            assert len(doc["spec"]["blocks"]) == 1 and doc["spec"]["blocks"][0]["markdown"] == (
                HERE / f"protocol.{lang}.md"
            ).read_text("utf-8")
            readback.append(dict(language=lang, text_equal=True, revision=doc["revision"]))
        save(
            work / "registration.json",
            dict(
                project=project["id"],
                record=recorder.experiment,
                pending=recorder.status["pending"],
                protocol_readback=readback,
            ),
        )
        base.atomic_json(work / "status.json", dict(state="registered", sequences_completed=0))
        print(json.dumps(load(work / "registration.json")), flush=True)


def frozen(work):
    assert load(work / "runner-manifest.json") == manifest(), "runner changed"
    assert load(work / "implementation.json") == implementation(), "implementation changed"
    assert load(work / "cases.json") == cases(), "cases changed"


def boundary(work):
    if (work / "STOP").exists():
        raise InterruptedError("complete boundary pause")
    base.resource_check(work)


def unit(work, key, student, operation):
    boundary(work)
    before = student.state()
    started = time.perf_counter()
    save(
        work / "in-flight.json",
        dict(
            key=key,
            pid=os.getpid(),
            created_at=psutil.Process().create_time(),
            time_us=student.core.time_us,
            before_sha256=base.digest(before),
        ),
    )
    result = operation()
    after = student.state()
    state_file = key + "/whole.json.gz"
    result_file = key + "/result.json.gz"
    a = save(work / state_file, after)
    b = save(work / result_file, result)
    save(
        work / key / "complete.json",
        dict(
            state_file=state_file,
            sha256=a["sha256"],
            result_file=result_file,
            result_sha256=b["sha256"],
            before_sha256=base.digest(before),
            after_sha256=base.digest(after),
            start_us=before["core"]["time_us"],
            end_us=student.core.time_us,
            wall_seconds=time.perf_counter() - started,
        ),
    )
    base.atomic_json(
        work / "current.json", dict(unit=key, state_file=state_file, sha256=a["sha256"], time_us=student.core.time_us)
    )
    (work / "in-flight.json").unlink()


def size(path):
    total = 0
    pending = [path]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
    return total


def run(work):
    with base.worker_lock(work):
        frozen(work)
        boundary(work)
        if load(work / "status.json") != dict(state="registered", sequences_completed=0):
            raise RuntimeError("fresh start only; inspect prior complete boundary")
        if (work / "in-flight.json").exists():
            raise RuntimeError("orphan in-flight; no replay")
        resource = base.resource_check(work)
        assert (
            resource["available_bytes"]["commit"] >= 8 * 2**30
            and resource["available_bytes"]["data_disk"] >= 34 * 2**30
        )
        save(
            work / "host.json",
            dict(pid=os.getpid(), created_at=psutil.Process().create_time(), command=psutil.Process().cmdline()),
        )
        rows = load(work / "cases.json")
        with base.Guard(work):
            for i, c in enumerate(rows):
                boundary(work)
                if i % 32 == 0 and size(work) > POLICY["originals_bytes"] - 128 * 2**20:
                    save(
                        work / "STOP",
                        dict(reason="originals budget with next-block allowance", epoch=time.time(), policy=POLICY),
                    )
                    raise InterruptedError("originals budget complete-boundary pause")
                s = Assay(c)
                key = "subjects/" + c["key"]
                save(work / key / "birth.json.gz", s.state())
                unit(work, key + "/teaching", s, s.teach)
                unit(work, key + "/probe", s, s.probe)
                base.atomic_json(work / "status.json", dict(state="running", sequences_completed=i + 1, last=c["key"]))
                if (i + 1) % 32 == 0:
                    print(json.dumps(dict(completed=i + 1, total=len(rows), last=c["key"])), flush=True)
            base.atomic_json(work / "status.json", dict(state="awaiting-analysis", sequences_completed=len(rows)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify", "prepare", "run", "status"))
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--instrument", type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == "verify":
        verify(args.instrument.resolve())
    elif args.command == "prepare":
        prepare(work, args.instrument.resolve())
    elif args.command == "run":
        run(work)
    else:
        print(
            json.dumps(
                dict(
                    status=load(work / "status.json") if (work / "status.json").exists() else None,
                    stop=(work / "STOP").exists(),
                    in_flight=(work / "in-flight.json").exists(),
                    resources=base.resource_check(work),
                )
            )
        )
