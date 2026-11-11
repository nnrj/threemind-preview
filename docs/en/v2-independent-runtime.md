# Independent Runtime and deployment checks

[中文](../zh/v2-independent-runtime.md)

Runtime retains stateful plastic kernels, buses, adapters, clocks, codecs, standalone SQLite recovery, and optional passive observers. Lab owns Web, PostgreSQL, research orchestration, notes, and reports. Models do not require Lab or cloud access. Observation and explicit intervention are optional tools, distinct from endogenous dynamics.

## Installation

For source development, install `python -m pip install -e packages/runtime` followed by `python -m pip install -e packages/transformer -e ".[dev]"` with the chosen project Python.

Build standalone wheels with `python scripts/build-python-packages.py --out .work/python-wheels`. Runtime's mandatory dependencies are NumPy, Arrow for the existing model format, Pydantic and psutil. It does not require Web, PostgreSQL, plotting or document-export packages. World and media extras are optional; install the Rust native extension separately or explicitly use `--backend reference`.

Example: `threemind-runtime --model model.tmind --backend reference --clock unbounded --until-us 1000000 --export continued.tmind`. The endpoint is an absolute simulation timestamp for this command, not a model lifespan. It must not precede the saved model time. Adapters and environments require explicit attachment. A model artifact stores Core and sensory configuration; exact embodied-experiment restoration additionally requires world, bus and observer context.

## Intervention declarations

Snapshots faithfully preserve silenced nodes and edges. Run `threemind-deployment model.tmind` to inspect them. Add `--output declaration.json` to write a new declaration. Models with masks require `--acknowledge-interventions`, or explicit unsilencing of a separate copy before export. No exporter silently clears masks.

Pass `--deployment-manifest declaration.json` to `threemind-runtime --model model.tmind` for exact artifact-hash, state-hash and mask verification. This prevents accidental deployment of a mismatched model; it is not a security boundary against an authorized user changing software. The historical CLI remains available for research reproduction.

## Optional external sandbox

`deploy/compose.runtime.yaml` uses the independent Python Runtime image with no network or added devices, read-only model input, a separate output directory, 4 GiB RAM and two CPU limits. Docker stays outside Core. Place the model and declaration under `deploy/runtime-input/`, create a container-writable `deploy/runtime-output/`, and configure an appropriate absolute endpoint. Run `docker compose -f deploy/compose.runtime.yaml run --rm runtime` for one finite job. Existing output files are not overwritten.

Robotics deployments require explicit device/network permissions and realtime scheduling. The template does not establish real-device correctness, production security or value alignment. These remain separate validations.
