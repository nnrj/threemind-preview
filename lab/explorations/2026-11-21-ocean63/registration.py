"""Storage admission and authenticated registration of the three water-world protocols."""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import os
import shutil
import socket
import threading
import time
from uuid import UUID, uuid5

from apparatus import *
from threemind_lab.config import load_env
from threemind_lab.experiment_storage import ExperimentStorage
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder

PROJECT = "d0a04159-ee0f-4200-ada9-13d5ce7197b7"
NS = UUID("028a8100-e58e-44f7-9f28-5c0819249b13")
BATCH = "ocean63-20261121"
PEAK_GIB = {"30": 9, "28": 6, "38": 14, "39C": 32}
TITLES = {"28": "有限能量、摄食与繁殖", "30": "内核、直接感官响应与随机动作的摄食比较", "38": "营养供给与亲代捕食行为", "39C": "可食遗体与多代环境选择"}


def pool():
    load_env()
    return ExperimentStorage(ResearchStorage(os.getenv("THREEMIND_STORAGE_CONTROL") or None))


def name(code):
    return "ocean63-" + code + "-20261121"


def directory(code):
    return pool().path(BATCH, "study-" + code.lower())


@contextmanager
def api():
    """Use the local API with its normal authentication and the configured project database."""
    import httpx
    from urllib.parse import urlsplit
    load_env()
    url = os.getenv("THREEMIND_API_URL", "http://127.0.0.1:8877")
    endpoint = urlsplit(url)
    with ExitStack() as stack:
        try:
            with socket.create_connection((endpoint.hostname, endpoint.port or 80), timeout=.5):
                pass
            transport = httpx.HTTPTransport(trust_env=False)
        except OSError:
            if endpoint.hostname not in ("127.0.0.1", "localhost"):
                raise
            # Task-private loopback socket. The workstation authenticates a real local
            # connection. Nothing binds its usual port or starts an experiment worker.
            import uvicorn
            from threemind_lab.api import create_app
            sock = stack.enter_context(socket.socket(socket.AF_INET,socket.SOCK_STREAM))
            sock.bind(("127.0.0.1",0))
            url = f"http://127.0.0.1:{sock.getsockname()[1]}"
            server = uvicorn.Server(uvicorn.Config(create_app(),log_level="error",access_log=False,ws="none"))
            thread = threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
            thread.start()
            def close_server():
                server.should_exit = True
                thread.join(timeout=15)
            stack.callback(close_server)
            deadline = time.monotonic()+30
            while not server.started:
                if not thread.is_alive() or time.monotonic()>deadline:
                    raise RuntimeError("isolated local API failed to start")
                time.sleep(.05)
            transport = httpx.HTTPTransport(trust_env=False)
        client = stack.enter_context(OperationsClient(url=url, username=os.getenv("THREEMIND_API_USERNAME"),
            password=os.getenv("THREEMIND_API_PASSWORD"), token=os.getenv("THREEMIND_API_TOKEN"),
            transport=transport, require_auth=True, source="ai"))
        yield client


def exclusive_json(path, value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2).encode("utf8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"frozen evidence differs: {path}")
        return
    with path.open("xb") as out:
        out.write(data)


def place():
    store = pool()
    state = store._read()
    parts = [dict(name="study-"+code.lower(), bytes=gib*GIB) for code,gib in PEAK_GIB.items()]
    if not store.preview(BATCH, parts)["fits"] and "portable-i" not in state["directories"]:
        options = [dict(v, id=k) for k,v in state["directories"].items()]
        options.append(dict(id="portable-i", path="I:/ThreeMindData", role="run", priority=30,
                            enabled=True, reserve_bytes=5*GIB))
        store.configure(options, expected_revision=state["revision"])
    binding = store.reserve(BATCH, parts, allow_split=False)
    assert len({part["directory"] for part in binding["parts"]}) == 1
    for code,gib in PEAK_GIB.items():
        folder = directory(code)
        folder.mkdir(parents=True, exist_ok=True)
        print(code, folder, gib, flush=True)


def register(codes):
    from _threemind_native import _threemind_native
    for code in codes:
        protocol = HERE / ("carrion-protocol.zh.md" if code == "39C" else "protocol.zh.md")
        text = protocol.read_text(encoding="utf8")
        folder = directory(code)
        source = folder/"frozen"
        source.mkdir(exist_ok=True)
        files = [HERE/n for n in ("apparatus.py","execution.py","baseline.py","registration.py")]
        if code == "39C":
            files += [HERE/"carrion.py", HERE/"extend.py"]
        files += [protocol, E28_INPUT, E30_INPUT, E37_INPUT, E38_INPUT]
        files += list(sorted((ROOT/"lab/tools").glob("ocean*.py")))
        for f in files:
            dst = source/f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile(f, dst)
            if sha(dst) != sha(f):
                raise ValueError(f"frozen source mismatch: {f}")
        frozen = {f.relative_to(ROOT).as_posix():sha(f) for f in files}
        frozen["_threemind_native"] = sha(Path(_threemind_native.__file__))
        exclusive_json(folder/"frozen.json", frozen)
        if (folder/"registration.json").exists():
            continue
        with api() as client:
            rec = ResearchRecorder(folder, PROJECT, client=client)
            key = name(code)
            rec.register(dict(source_key=key, title=f"OCEAN63-{code} "+TITLES[code],
                classification="formal", execution_status="running", executor="ai", kernels=[KERNEL],
                protocol=text, protocol_version=sha(protocol),
                required_roles=["protocol","report","original","note"],
                metadata=dict(historical=["E38"] if code == "39C" else ["E"+code],kernel=KERNEL,birth_rule="threemind.birth/2",
                              reserve_GiB=PEAK_GIB[code])),
                request_id=uuid5(NS,key+"-register"))
            rec.text(dict(identity=str(uuid5(NS,key+"-protocol-doc")),request_id=str(uuid5(NS,key+"-protocol")),
                       expected_revision=0,kind="protocol",title=f"OCEAN63-{code} protocol",markdown=text))
            rec.synchronize(strict=True)
            assert rec.status["pending"] == 0
            exclusive_json(folder/"registration.json",dict(project=PROJECT,record=rec.experiment,
                      registered_utc=datetime.now(timezone.utc).isoformat(),pending=0,protocol_sha256=sha(protocol)))
            print(code,rec.experiment,flush=True)


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("place", "register"))
    p.add_argument("codes", nargs="*")
    args=p.parse_args()
    place() if args.operation=="place" else register(args.codes or ["30","28","38"])
