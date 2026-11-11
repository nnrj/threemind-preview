"""Explicit local capability probes; no model, database, camera or microphone IO.

Reports describe the process executing the probe. They are not assertions about
another host or guarantees that every possible media file can be decoded.
"""

import io
import json
import platform
import subprocess
import sys
import time
import wave
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version


def kernel_feature(kernel_id):
    """Match the scheduler's identity, including a kernel's minor version.

    Splitting on every dot would reduce both memory/3.1 and memory/5.1 to
    ``1`` and advertise neither required capability. Only strip the namespace.
    """
    return "worker.kernel_" + kernel_id.removeprefix("threemind.").replace("/", "")


def package(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def check(label, operation):
    start = time.perf_counter()
    try:
        detail = operation() or {}
        return {
            "name": label,
            "state": "available",
            "reason": "检查通过",
            **detail,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
        }
    except Exception as error:  # noqa: BLE001 -- a capability boundary records optional native failures
        # Optional native libraries can expose their own Exception subclasses
        # (for example mujoco.FatalError). Do not take down unrelated workers.
        return {
            "name": label,
            "state": "unavailable",
            "reason": f"{type(error).__name__}: {error}"[:400],
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
        }


def wav_probe():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\0\0")
    stream.seek(0)
    with wave.open(stream, "rb") as reader:
        if reader.readframes(1) != b"\0\0":
            raise ValueError("PCM WAV memory roundtrip failed")
    return {"check": "one-sample in-memory PCM WAV roundtrip", "formats": ["pcm-wav"]}


def image_probe():
    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(stream, format="PNG")
    stream.seek(0)
    with Image.open(stream) as image:
        if image.convert("RGB").getpixel((0, 0)) != (0, 0, 0):
            raise ValueError("PNG memory roundtrip failed")
    return {"check": "one-pixel in-memory PNG roundtrip", "package": package("Pillow")}


def av_probe(names):
    import av

    codecs, unavailable = [], {}
    for name in names:
        try:
            av.codec.Codec(name, "r")
            codecs.append(name)
        except (ValueError, RuntimeError) as error:
            unavailable[name] = str(error)[:160]
    return {
        "state": "available" if len(codecs) == len(names) else "partial" if codecs else "unavailable",
        "reason": "已检查已注册解码器；实际载体仍须通过解码与预算校验。",
        "codecs": codecs,
        "unavailable_codecs": unavailable,
        "package": package("av"),
        "check": "import and decoder registration lookup",
    }


def network_probe():
    import websockets

    return {
        "package": websockets.__version__,
        "check": "WebSocket transport import; access depends on deployment and device credentials",
    }


def probe_api():
    pcm = check("PCM WAV", wav_probe)
    audio = check("压缩音频解码", lambda: av_probe(("mp3", "aac", "flac")))
    audio["pcm_wav"] = pcm
    if audio["state"] == "unavailable" and pcm["state"] == "available":
        audio |= {"state": "partial", "reason": "PCM WAV 可用；压缩音频不可用。" + audio["reason"]}
    image = check("图片解码", image_probe)
    video = check("视频解码", lambda: av_probe(("h264", "vp9", "mpeg4")))
    if image["state"] != "available":
        video |= {"state": "unavailable", "reason": "视频视觉帧还依赖图像转换：" + image["reason"]}
    return {
        "schema": "threemind.capabilities/1",
        "scope": "api",
        "checked_at": datetime.now(UTC).isoformat(),
        "platform": platform.system(),
        "python": platform.python_version(),
        "features": {
            "api.media_audio": audio,
            "api.media_image": image,
            "api.media_video": video,
            "api.network": check("设备 WebSocket", network_probe),
        },
    }


def engine_probe(backend):
    from .host import create_engine

    engine = create_engine(backend=backend)
    engine.advance_to(1000)
    if engine.time_us != 1000:
        raise ValueError("independent engine time smoke check failed")
    return {"backend": backend, "check": "independent empty engine advances to 1000 us"}


def physics_probe():
    from .adapters import PlanarBody

    body = PlanarBody(0)
    stimulus = body.sample(0)
    if stimulus.time_us != body.period_us:
        raise ValueError("physical environment clock smoke check failed")
    return {"package": package("mujoco"), "check": "independent built-in planar body takes one physical interval"}


def world_probe(rgb=False):
    from .world import PhysicalWorld
    from .world_schema import CameraSensor, default_world

    spec = default_world()
    if rgb:
        spec.sensors.append(CameraSensor(id="probe_camera", port=10, body_id="body"))
    with PhysicalWorld(spec, 0) as world:
        event = world.sample(0)
        if event.time_us != world.period_us:
            raise ValueError("world sensory boundary probe failed")
        return {
            "package": package("mujoco"),
            "rgb": rgb,
            "render_calibration": world.render_calibration,
            "check": "headless declared world takes one physical interval",
        }


def world_rgb_probe():
    # Driver faults, missing display contexts and hangs stay outside the worker.
    # The child inherits the exact selected GL backend; never silently try a
    # different renderer, which could change pixels used as sensory input.
    result = subprocess.run(
        [sys.executable, "-m", "threemind_runtime.capability_render"],
        # The probe consumes no input. Inheriting a worker's parent-watch pipe
        # can stall the Windows venv launcher while another thread reads it.
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(f"isolated RGB probe exited {result.returncode}: {result.stderr[-800:]}")
    value = json.loads(result.stdout)
    if (
        not isinstance(value, dict)
        or value.get("schema") != "threemind.render-probe/1"
        or not isinstance(value.get("result"), dict)
        or value["result"].get("state") not in ("available", "unavailable")
    ):
        raise ValueError("invalid isolated RGB probe response")
    return value["result"] | {"isolated_process": True}


def probe_worker(backend):
    from .telemetry_probe import SystemTelemetryProbe

    def telemetry():
        host, process = SystemTelemetryProbe().collect(time.perf_counter())
        return {
            "readings": {
                scope: {
                    name: {"available": r.available, "reason": r.unavailable_reason, "unit": r.unit}
                    for name, r in readings.items()
                }
                for scope, readings in (("host", host), ("process", process))
            }
        }

    features = {
        "worker.core": check("运行内核", lambda: engine_probe(backend)),
        "worker.mujoco": check("MuJoCo 物理环境", physics_probe),
        "worker.world_v1": check("可配置世界与躯体", world_probe),
        "worker.world_rgb_v1": check("世界离屏 RGB 感官", world_rgb_probe),
    }
    from .robot import RobotWorld
    from .robot_assets import installed
    from .robot_assets import registry as robot_assets
    from .robot_templates import custom_arm

    def robot_probe():
        with RobotWorld(custom_arm(), 0) as world:
            world.sample(0)
            return {"schema": "threemind.robot-task/1", "motors": world.model.nu}

    features["worker.robot_v1"] = check("机器人任务与控制", robot_probe)
    from .playground_assets import probe as playground_probe

    for implementation, device in (("jax", "cpu"), ("jax", "cuda"), ("warp", "cuda")):
        features[f"worker.playground_{implementation}_{device}"] = check(
            f"Playground {implementation}/{device}",
            lambda implementation=implementation, device=device: playground_probe(implementation, device),
        )
    for asset_id in robot_assets()["profiles"]:
        features["worker.robot_asset_" + asset_id] = {
            "name": asset_id, "state": "available" if installed(asset_id) else "unavailable",
            "reason": "Pinned assets are verified locally; no implicit download.",
        }
    from threemind_kernels.registry import kernel_catalog, resolve_kernel

    for candidate in kernel_catalog():
        if candidate["default"]:
            continue
        identity = candidate["kernel_id"]
        feature = kernel_feature(identity)
        features[feature] = check(
            candidate["title"], lambda identity=identity: resolve_kernel(identity).create(backend=backend).metrics()
        )
    measured = check("宿主与进程计数能力", telemetry)
    for scope, title in (("host", "宿主物理遥测"), ("process", "工作进程遥测")):
        readings = measured.get("readings", {}).get(scope, {})
        available = sum(r["available"] for r in readings.values())
        features[f"worker.telemetry_{scope}"] = {
            "name": title,
            "state": "available"
            if readings and available == len(readings)
            else "partial"
            if available
            else "unavailable",
            "reason": "只报告当前计数可用性，不保存读数；速率项可能正在建立基线。" if readings else measured["reason"],
            "readings": readings,
            "available_count": available,
            "total_count": len(readings),
        }
    features["worker.telemetry_runtime"] = {
        "name": "意识执行反馈",
        "state": "available" if hasattr(time, "thread_time") else "partial",
        "reason": "实际实例指标仅在模型执行后产生；此处只检查高精度计时 API。",
        "thread_cpu_clock": hasattr(time, "thread_time"),
        "wall_clock": "perf_counter",
    }
    return {
        "schema": "threemind.capabilities/1",
        "scope": "worker",
        "backend": backend,
        "checked_at": datetime.now(UTC).isoformat(),
        "platform": platform.system(),
        "python": platform.python_version(),
        "features": features,
    }
