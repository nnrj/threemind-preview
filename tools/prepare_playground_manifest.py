"""Build reviewed package metadata from the pinned public checkouts (no downloads)."""

import json
import subprocess
from pathlib import Path

import mujoco

from threemind_runtime.robot_assets import describe_model

ROOT = Path(__file__).resolve().parents[1]
REVISION = "ef4fefc13033c0468af4ef651847f5348af0c7d7"
MENAGERIE = "1b86ece576591213e2b666ebf59508454200ca97"


def tree(root, revision, prefix):
    lines = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-rl", revision, "--", prefix], text=True)
    result = []
    for line in lines.splitlines():
        meta, path = line.split("\t")
        _, kind, sha, size = meta.split()
        assert kind == "blob"
        result.append({"path": path, "git_blob": sha, "bytes": int(size)})
    return result


def main():
    upstream, assets = ROOT / ".work/playground-source", ROOT / ".work/playground-menagerie"
    files = tree(upstream, REVISION, "mujoco_playground")
    # Source code and Panda-specific XML are pinned independently of package version.
    files = [r for r in files if r["path"].endswith(".py") or "/franka_emika_panda/xmls/" in r["path"]]
    files += tree(upstream, REVISION, "LICENSE")
    models = tree(assets, MENAGERIE, "franka_emika_panda")
    source_xml = upstream / "mujoco_playground/_src/manipulation/franka_emika_panda/xmls"
    model_files = assets / "franka_emika_panda"
    content = {
        p.name: p.read_bytes()
        for folder in (model_files, model_files / "assets", source_xml)
        for p in folder.iterdir()
        if p.is_file()
    }
    model = mujoco.MjModel.from_xml_string((source_xml / "mjx_single_cube.xml").read_text(), assets=content)
    world, names = describe_model(model)
    world.physics.step_us, world.physics.sample_us = 5000, 20000
    world.wiring_namespace = "playground-panda-v1"
    world.label = "PandaPickCube declared sensory and action ports"
    # Material mechanics always come from upstream XML; this is observer/port metadata.
    values = {
        "schema": "threemind.playground-assets/1",
        "revision": REVISION,
        "menagerie_revision": MENAGERIE,
        "source_files": files,
        "asset_files": models,
        "world": world.model_dump(mode="json"),
        "object_names": names,
        "endpoint": next(k[2:] for k, i in names.items() if k.startswith("b_") and model.body(i).name == "hand"),
        "object_body": next(k[2:] for k, i in names.items() if k.startswith("b_") and model.body(i).name == "box"),
    }
    path = ROOT / "src/threemind_runtime/playground_assets.json"
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "source_files": len(files),
            "asset_files": len(models),
            "asset_bytes": sum(r["bytes"] for r in models),
            "motors": model.nu,
        }
    )


if __name__ == "__main__":
    main()
