# ThreeMind

[中文](README_CN.md) | [English](README.md)

ThreeMind is a local research environment for experimenting with a continuous,
plastic associative network. Its ultimate engineering objective is to create
artificial consciousness. It does not claim that the current implementation has
already achieved or proven that objective. Its purpose is to make the dynamics,
input boundaries, memory-like consolidation, forgetting, structural readouts,
and experimental controls inspectable.

[Hypothesis framework](docs/en/consciousness-hypothesis.md) · [Architecture](docs/en/architecture-boundaries.md) · [Multimodal senses and outputs](docs/en/multimodal-sensory-and-output-adapters.md) · [ThreeJSON visualization boundary](docs/en/threejson-visualization-boundary.md) · [Research notes](docs/en/research-notes.md) · [Archive catalogue](docs/en/archive-catalog.md) · [Experiment & Debug Workbench](docs/en/experiment-debugger.md)

[Temporal frame transport](docs/en/temporal-frame-transport.md) · [时间帧传输与流量控制](docs/zh/temporal-frame-transport.md)

## Start here

ThreeMind has two decoupled projects:

- **Core**: Python runtime, API, CLI, model packages, adapters, persistence.
- **UI**: a React + Vite client in `threemind-ui/`; it never contains Core rules.

### 1. Install the Core

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The editable installation is important: it exposes both the Core package and
the sibling `adapters/` package. It also installs the canonical `threemind`
command and its shorter `mind` alias; both invoke the same CLI implementation.
Install the optional full telemetry backend when disk, network, battery, and
whole-process counters are needed:

```powershell
python -m pip install -e ".[telemetry]"
```

Install the optional non-semantic media codecs when compressed audio, images,
or video should be uploaded. Standard PCM WAV and live browser PCM/grayscale
streams continue to work without this extra:

```powershell
python -m pip install -e ".[media]"
```

### 2. Run the Core

```powershell
python -m threemind serve
```

The local API is available at `http://127.0.0.1:8877`.

Use another port if needed:

```powershell
python -m threemind serve --port 8899
```

### 3. Run the React UI

In a second terminal:

```powershell
cd threemind-ui
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://127.0.0.1:3001`.
The UI proxies `/api` and WebSocket requests to the local Core by default.

For a production bundle:

```powershell
cd threemind-ui
npm run build
```

Serve `threemind-ui/dist/` with any static server. When the UI and Core use
different origins, configure `VITE_THREEMIND_API` with the Core base URL.

### Convenience development launcher

`scripts/dev.ps1` starts two visible terminal processes. It is optional; the
Core and UI remain independent processes.

## What runs inside ThreeMind

```text
external carrier / environment / remote device
  -> sensory or body adapter
  -> anonymous SensoryFrame and InputBus
  -> transparent gate / optional environmental selector
  -> associative Core runtime
  -> anonymous OutputFrame and OutputBus
  -> readout, visualizer, interpreter, tool, or remote-output adapter
```

Important boundaries:

- The anonymous Core does **not** store input text inside nodes or edges.
- Text is only one experimental carrier. The auditory and visual adapters now
  encode uploaded or live audio, images, and video into anonymous channels;
  tools and future senses use the same boundary.
- The default background is measured host telemetry, sampled once per second
  and mapped per consciousness to anonymous channels. Random ambient input and
  whole-process self telemetry are separate, default-off adapters.
- The optional body adapter can still filter a random ambient field through
  sampling, threshold, adaptation, and noise before the Core sees it.
- The Core gate is transparent by default: it does not pre-rank channels using
  relevance, novelty, or a fixed channel bias. Optional environmental plugins
  must explicitly enable competition; they can constrain anonymous drive or
  capacity, but cannot create semantic goals or edit graph state.
- Default-on, switchable topology-local inhibition can diffuse a finite, decaying,
  delayed potential over physical adjacency without reversing directed
  excitatory edges. It remains independent of the legacy global clamp.
- Default-off energy accounting has no internal recovery. Only an explicit
  initial reserve and an external finite supply adapter can increase its
  experimental scalar. Measured CPU, memory, disk, network, and power state are
  ordinary external sensations and never become Core energy.
- Output adapters read an anonymous activity projection. Transport clients may
  receive it in acknowledged chunks, but chunking never removes nodes or edges.
  A readable phrase is an adapter-level observation, not proof that words
  exist in Core.

See [architecture boundaries](docs/en/architecture-boundaries.md) for the
complete rationale and [research notes](docs/en/research-notes.md) for the
working hypothesis and interpretation cautions.

The optional mechanisms and their observation interface are specified in
[Local Inhibition, Optional Energy Accounting, and Dynamics
Tracing](docs/en/local-inhibition-energy-and-dynamics.md).

## Main UI workflow

1. Open **意识图像** and choose **开启新意识**.
2. Give the instance a name, select V1/V2/V3 if desired, or use the default
   V3 anonymous spatial model. Spatial embedding is enabled by default.
3. Expand **高级设置** only when you want to change attention, association,
   propagation, learning, forgetting, consolidation, or capacity parameters.
4. Use the right-side panels to observe, control lifecycle/snapshots, and send
   stimuli. Host physical telemetry is enabled by default; random ambient input
   and whole-process self telemetry are opt-in and independently switchable.
   The `+`, Ear, and Eye controls submit media or explicitly start live capture;
   Mouth and Image subscribe to anonymous output projections.
5. Use **设置** for visualization, runtime sources, body and attention plugins,
   model parameters, AI providers, passive readout criteria, persistence,
   notifications, and network transport.
6. Use the top-level management pages for instances, packages, stimuli, and
   interpretation history. Use **Experiments** for a manual or AI-planned,
   command-audited protocol against an isolated clone by default. See the
   [Experiment & Debug Workbench](docs/en/experiment-debugger.md).
7. Use **Statistics & Evidence** for dynamics plots, recurrent-structure
   catalogues, temporal convergence, paired ablation, and checksum-protected
   research-data export. Per-tick plots require detailed tracing to be enabled
   before the experiment.

The passive structural readout is an output-bus consumer. Repeated structures,
activity, and delayed responses are observations to compare experimentally;
they are not by themselves evidence of intention or sentience.

## Model packages, snapshots, and persistence

Each `.tmind` model package is a ZIP archive containing a declarative
`manifest.json` and runtime state. A package never contains executable model
code. It can describe anonymous/labeled payload mode, weighted connections,
spatial embedding, and runtime parameters.

Pre-rename `.bbx` artifacts remain readable and indexable so existing
experiments are not lost. Importing one normalizes its filename to `.tmind`;
ThreeMind writes only `.tmind` packages.

The UI and API support package browsing, import, export, cloning, loading,
snapshots, portraits, comparison, signatures, and history. Current local
persistence choices are file, SQLite, MySQL, and Cloudflare D1 adapters.

For responsive local archive management, ThreeMind uses a dedicated local SQLite
metadata catalogue (`data/archive-index.sqlite3`) while `.tmind` files remain the
portable source of complete experimental state. Historical packages are indexed
in the background rather than scanned by live control endpoints. See
[Archive Catalogue and Non-blocking Persistence](docs/en/archive-catalog.md).

The default data directory is `data/`, resolved relative to this project. Use
`THREEMIND_DATA` or `threemind serve --data-dir <path>` to override it.
On the first backend start, ThreeMind creates `data/ui-settings.json` with the
complete defaults if and only if that file is absent. An existing file is never
overwritten during startup. The tracked `data/ui-settings.example.json` lists
the available public settings and adapter defaults; credentials remain in the
separate encrypted stores.

## CLI essentials

```powershell
python -m threemind create data\empty.tmind --name "First consciousness" --spatial-dimensions 3
python -m threemind inspect data\empty.tmind
python -m threemind stimulate data\empty.tmind "an external signal" --step 3
python -m threemind clone data\empty.tmind data\clone.tmind --name "A clone"
python -m threemind list data
python -m threemind instances
python -m threemind history interpretations --page 1 --page-size 50
```

After installation, the equivalent short form is available as `mind`, for
example `mind serve`. Documentation and automation use `threemind` as the
canonical, collision-resistant command name.

The HTTP API exposes equivalent runtime, instance, package, history, AI, and
settings operations. `GET /api/health` is a lightweight service check.

## AI services and secret handling

AI providers are optional. Environment generation contributes an ordinary
external stimulus; an AI interpreter is an external observer and its output is
stored as a log. Neither is allowed to write directly into Core nodes or edges.

Provider credentials and the optional network token are encrypted at rest with
Fernet. The key is stored in `data/.threemind.key` unless `THREEMIND_SECRET` is
provided by the deployment. API responses expose only configuration status,
never the secret values.

## Optional network transport

Network transport is disabled by default. Enable and configure it in
**设置 → 网络适配器**, including a shared token.

- WebSocket input: `/api/network/input`
- WebSocket output: `/api/network/output`
- Protocol: `threemind-network/1`

Network input accepts only anonymous sensory channels. Remote modulation is
separately opt-in and may only send scalar gain/budget values to a restricted
attention plugin. For remote access, serve behind TLS and keep the token secret.
Detailed envelopes and security limits are in
[the architecture document](docs/en/architecture-boundaries.md#network-transport-boundary).

## Documentation map

| Topic | English | 中文 |
| --- | --- | --- |
| Operating guide | [operations](docs/en/operations.md) | [操作指南](docs/zh/operations.md) |
| Architecture and protocol | [architecture boundaries](docs/en/architecture-boundaries.md) | [架构边界](docs/zh/architecture-boundaries.md) |
| Multimodal sensory and output adapters | [multimodal senses and outputs](docs/en/multimodal-sensory-and-output-adapters.md) | [多模态感官与输出器官](docs/zh/multimodal-sensory-and-output-adapters.md) |
| Physical telemetry sensory adapters | [physical telemetry](docs/en/physical-telemetry-sensory-adapters.md) | [物理遥测感官适配器](docs/zh/physical-telemetry-sensory-adapters.md) |
| Archive catalogue | [archive catalogue](docs/en/archive-catalog.md) | [归档目录与非阻塞持久化](docs/zh/archive-catalog.md) |
| Spatial embedding decision | [spatial embedding](docs/en/spatial-embedding-decision.md) | [空间基底决策](docs/zh/spatial-embedding-decision.md) |
| Foundational hypothesis | [consciousness hypothesis](docs/en/consciousness-hypothesis.md) | [意识假设纲要](docs/zh/consciousness-hypothesis.md) |
| Hypothesis and cautions | [research notes](docs/en/research-notes.md) | [研究笔记](docs/zh/research-notes.md) |
| Experiment and Debug Workbench | [experiment debugger](docs/en/experiment-debugger.md) | [实验与调试工作台](docs/zh/experiment-debugger.md) |
| Temporal frame transport and flow control | [temporal frame transport](docs/en/temporal-frame-transport.md) | [时间帧传输与流量控制](docs/zh/temporal-frame-transport.md) |
| Snapshot and temporal-window readouts | [temporal-window readout](docs/en/temporal-window-readout.md) | [时间区间收敛读出](docs/zh/temporal-window-readout.md) |
| Local inhibition, energy, and dynamics tracing | [inhibition, energy & dynamics](docs/en/local-inhibition-energy-and-dynamics.md) | [局部抑制、能量与动力学追踪](docs/zh/local-inhibition-energy-and-dynamics.md) |
| Statistics, evidence, and data export | [statistics and evidence](docs/en/statistics-and-evidence.md) | [统计与证据](docs/zh/statistics-and-evidence.md) |
| Intervention and paired ablation | [intervention and ablation](docs/en/intervention-and-ablation.md) | [干预与消融](docs/zh/intervention-and-ablation.md) |
| Research positioning and literature memo | [literature memo](docs/en/literature-positioning.md) | [研究定位与文献备忘](docs/zh/literature-positioning.md) |
| Mechanism comparison with existing networks | [algorithmic comparison](docs/en/algorithmic-comparison.md) | [算法机制对比](docs/zh/algorithmic-comparison.md) |
| Transformer comparison and research path | [assessment](docs/en/transformer-comparison-and-research-assessment.md) | [比较与研究路径评估](docs/zh/transformer-comparison-and-research-assessment.md) |
| Research self-assessment and evidence boundaries | [self-assessment](docs/en/research-self-assessment.md) | [研究自省与证据边界](docs/zh/research-self-assessment.md) |
| Experiment notebook and cross-experiment memos | [lab notebook](lab/README.md), [memos](lab/memos/README.md) | [实验日志](lab/README_CN.md)、[备忘](lab/memos/README_CN.md) |
| Paper workspace and terminology | [paper workspace](docs/paper/README.md), [terminology](docs/en/terminology.md) | [论文工作区](docs/paper/README_CN.md), [术语表](docs/zh/terminology.md) |

The research notes retain the still-valid experimental discipline from the
archived ThreeMind baseline, while intentionally omitting its superseded UI, API,
and storage instructions.
