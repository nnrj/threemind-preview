"""Pinned, bounded robot assets. Loading never implicitly downloads code or data."""

import hashlib
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .world_schema import digest


def registry():
    return json.loads(Path(__file__).with_name("robot_assets.json").read_text(encoding="utf-8"))


def cache_root():
    return Path(os.environ.get("THREEMIND_ROBOT_ASSETS", ".work/robot-assets-cache")).resolve()


def profile(identity):
    catalog = registry()
    if identity not in catalog["profiles"]:
        raise ValueError("unknown pinned robot asset")
    value = catalog["profiles"][identity] | {"revision": catalog["revision"], "repository": catalog["repository"]}
    return value | {"sha256": digest(value)}


def _path(root, relative):
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()) or Path(relative).is_absolute() or ":" in relative:
        raise ValueError("robot asset path escapes package")
    return result


def _valid(path, record):
    if not path.is_file() or path.stat().st_size != record["bytes"]:
        return False
    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() == record["git_blob"]


def installed(identity):
    value = profile(identity)
    root = cache_root() / value["revision"] / value["folder"]
    return all(_valid(_path(root, r["path"]), r) for r in value["files"])


def install(identity):
    value = profile(identity)
    if sum(r["bytes"] for r in value["files"]) > 256 * 1024 * 1024:
        raise ValueError("asset download exceeds 256 MiB")
    root = cache_root() / value["revision"] / value["folder"]
    root.mkdir(parents=True, exist_ok=True)
    for record in value["files"]:
        path = _path(root, record["path"])
        if _valid(path, record):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{value['revision']}/{value['folder']}/{record['path']}"
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(record["bytes"] + 1)
        actual = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        if len(content) != record["bytes"] or actual != record["git_blob"]:
            raise ValueError("downloaded asset size or pinned Git hash differs")
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_bytes(content)
        temporary.replace(path)
    return {"asset_id": identity, "asset_sha256": value["sha256"], "bytes": sum(r["bytes"] for r in value["files"])}


def load(identity, expected_hash):
    import mujoco

    value = profile(identity)
    if value["sha256"] != expected_hash:
        raise ValueError("robot asset identity differs; no silent upgrade")
    if not installed(identity):
        raise ValueError(f"Robot assets missing/corrupt. Install explicitly: threemind-robot assets install {identity}")
    root = cache_root() / value["revision"] / value["folder"]
    # Only pinned reviewed assets may reach the native parser. Reject path escape
    # and executable extension points even if a future registry is added.
    for row in value["files"]:
        if not row["path"].endswith(".xml"):
            continue
        document = ET.parse(_path(root, row["path"]))
        for element in document.iter():
            if element.tag in ("plugin", "extension"):
                raise ValueError("robot package plugins are not supported")
            if "file" in element.attrib:
                _path(root, element.attrib["file"])
    return mujoco.MjModel.from_xml_path(str(_path(root, value["entry"])))


def describe_model(model):
    """Generate explicit anonymous wiring, retaining physical joint force limits."""
    import mujoco

    from .world_schema import Body, Geometry, InertialSensor, Joint, JointSensor, Motor, Physics, WorldSpec

    data = mujoco.MjData(model)
    if model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, 0)
    names = {}
    bodies, joints, motors, sensors, geometries = [], [], [], [], []
    for i in range(1, model.nbody):
        identity = f"body{i}"
        names["b_" + identity] = i
        parent = int(model.body_parentid[i])
        bodies.append(
            Body(id=identity, label=model.body(i).name or identity, parent_id=f"body{parent}" if parent else None)
        )
    for i in range(model.njnt):
        if model.jnt_type[i] not in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE):
            continue
        identity = f"joint{i}"
        names["j_" + identity] = i
        initial = float(data.qpos[model.jnt_qposadr[i]])
        limits = tuple(float(v) for v in model.jnt_range[i]) if model.jnt_limited[i] else (-100000.0, 100000.0)
        joints.append(
            Joint(
                id=identity,
                label=model.joint(i).name or identity,
                body_id=f"body{model.jnt_bodyid[i]}",
                kind="hinge" if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_HINGE else "slide",
                axis=tuple(float(v) for v in model.jnt_axis[i]),
                limits=limits,
                initial=min(limits[1], max(limits[0], initial)),
            )
        )
        for kind, scale in (("joint_position", 3.0), ("joint_velocity", 5.0)):
            sensors.append(
                JointSensor(id=kind + identity, port=len(sensors), kind=kind, joint_id=identity, scale=scale)
            )
    for i in range(model.nu):
        if model.actuator_trntype[i] != mujoco.mjtTrn.mjTRN_JOINT:
            raise ValueError("robot actuator transmission requires a dedicated adapter")
        identity = f"motor{i}"
        names["a_" + identity] = i
        joint = int(model.actuator_trnid[i, 0])
        force_range = (
            model.actuator_forcerange[i]
            if model.actuator_forcelimited[i]
            else model.jnt_actfrcrange[joint]
            if model.jnt_actfrclimited[joint]
            else None
        )
        if force_range is None or force_range[0] >= 0 or force_range[1] <= 0:
            raise ValueError("asset must declare a physical actuator force range")
        if model.actuator_gear[i, 0] <= 0 or any(model.actuator_gear[i, 1:]):
            raise ValueError("non-scalar or negative robot gear needs a dedicated adapter")
        motors.append(
            Motor(
                id=identity,
                label=model.actuator(i).name or identity,
                port=i,
                joint_id=f"joint{joint}",
                gear=float(model.actuator_gear[i, 0]),
                control_limit=float(min(-force_range[0], force_range[1])),
            )
        )
    for i in range(model.ngeom):
        identity = f"geom{i}"
        names["g_" + identity] = i
        # Mechanics come from the pinned model; exact render meshes are exported
        # separately. These descriptors only bind sensor IDs/observer transforms.
        geometries.append(
            Geometry(
                id=identity,
                body_id=f"body{model.geom_bodyid[i]}" if model.geom_bodyid[i] else None,
                label=model.geom(i).name or identity,
            )
        )
    for i in range(model.nsensor):
        kind = {
            int(mujoco.mjtSensor.mjSENS_ACCELEROMETER): "accelerometer",
            int(mujoco.mjtSensor.mjSENS_GYRO): "gyroscope",
        }.get(int(model.sensor_type[i]))
        if kind:
            identity = f"inertial{i}"
            names["s_" + identity] = i
            site = int(model.sensor_objid[i])
            sensors.append(
                InertialSensor(
                    id=identity,
                    port=len(sensors),
                    kind=kind,
                    body_id=f"body{model.site_bodyid[site]}",
                    scale=9.81 if kind == "accelerometer" else 3.0,
                )
            )
    return WorldSpec(
        schema_id="threemind.world/2",
        label="Pinned robot wiring",
        physics=Physics(step_us=2000, sample_us=10000),
        bodies=bodies,
        joints=joints,
        motors=motors,
        sensors=sensors,
        geometries=geometries,
    ), names


def task_for_asset(identity):
    from .robot_protocol import RobotControl, RobotTask

    value = profile(identity)
    model = load(identity, value["sha256"])
    world, names = describe_model(model)
    endpoint = next(
        (k[2:] for k, i in names.items() if k.startswith("b_") and model.body(i).name == value["endpoint"]), None
    )
    if endpoint is None:
        # Stable documented distal actuator body when the vendor name is absent.
        endpoint = f"body{model.jnt_bodyid[model.actuator_trnid[-1, 0]]}"
    world.wiring_namespace = "menagerie-" + identity + "-v1"
    return RobotTask(
        name=identity + " interface observation",
        body_id="menagerie-" + identity + "/1",
        category=value["category"],
        world=world,
        objective="observe",
        endpoint_body=endpoint,
        asset_id=identity,
        asset_sha256=value["sha256"],
        control=RobotControl(mode=value["modes"][0]),
    )
