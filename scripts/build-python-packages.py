"""Build self-contained Runtime and Lab wheels without duplicated package ownership.

Runtime sources stay at their established import paths. Staging makes the wheel
build independent of parent paths; no live environment is installed or altered.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / ".work/python-wheels")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / ".work").mkdir(exist_ok=True)
    for kind, packages, manifest in (
        (
            "runtime",
            ("threemind_core", "threemind_kernels", "threemind_runtime"),
            ROOT / "packages/runtime/pyproject.toml",
        ),
        ("transformer", ("threemind_transformer",), ROOT / "packages/transformer/pyproject.toml"),
        ("lab", ("threemind_lab",), ROOT / "pyproject.toml"),
    ):
        with tempfile.TemporaryDirectory(prefix=f"wheel-{kind}-", dir=ROOT / ".work") as temporary:
            stage = Path(temporary)
            if not stage.resolve().is_relative_to((ROOT / ".work").resolve()):
                raise ValueError("build staging escaped the workspace")
            (stage / "pyproject.toml").write_text(
                manifest.read_text(encoding="utf-8").replace('"../../src"', '"src"'), encoding="utf-8"
            )
            for package in packages:
                shutil.copytree(
                    ROOT / "src" / package,
                    stage / "src" / package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(output),
                    str(stage),
                ],
                check=True,
            )


if __name__ == "__main__":
    main()
