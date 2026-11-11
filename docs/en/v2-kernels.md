# Multiple kernels, a local Transformer and standalone deployment

## Added 11 November 2026: /5.3 and faithful /5.2

The registry now includes independent /5.3 Python/Rust and faithful /5.2 Rust backends. The global default remains /3. The earlier seven-kernel overview below is retained; new versions, builds and results are in the [/5.3 delivery](v2-kernel53.md). Running services were not automatically restarted.

[中文](../zh/v2-kernels.md) · [Implementation and acceptance](plans/multi-kernel-implementation.md) · [Principles](kernel-evolution-principles.md)

## Choosing a kernel

Select one of seven kernels in **Kernels and comparison tools**, or the first level of Create consciousness. New creation still defaults to activity-dependent retention in `continuous-memory/3`; the new local-event `/4` is explicitly selectable, and previous versions remain available. Ordinary consciousnesses still default to unlimited duration. Sensory marking mode remains visible. Kernel identity is fixed at creation; existing models are neither upgraded nor converted automatically.

| Identity | Mechanisms | Observation |
| --- | --- | --- |
| `threemind.causal/9` | Preserved V3 restoration, original hypotheses and `state/6` | Original activation, temporal convergence, support, stability and ledgers |
| `threemind.continuous/1` | Original rules plus independently ablatable short-term synaptic resources, fast traces and receiver-local context | Activation plus the new resource, trace and allocation evidence |
| `threemind.continuous-memory/1` | Continuous candidate with independently controlled depletion, facilitation and consolidation | Separate and combined effects on short and long timescales |
| `threemind.continuous-memory/2` | Memory/1 plus local novelty settlement from actual delayed arrivals; immediate evaluation remains selectable | Reentry, birth bonuses and complete trajectories; see [calibration](v2-memory-calibration.md) |
| `threemind.continuous-memory/3` (new default) | Activity-dependent edge/support half-lives, automatic reclamation and recoverable strong-input fatigue; dormancy/revival off | Retention, reclamation and cost; [parameters](plans/memory-retention-v3.md), [verification](../../lab/explorations/2026-10-08-retention-kernel/report.en.md) |
| `threemind.lif/1` | Independent membrane, current, spikes and local timing learning | Raw mV, nA and spike times; graphics use a declared depolarization projection |
| `threemind.continuous-memory/4` (research option) | Object-local decay, emission/expiry events, unified reception, local resource field and explicit controls | [Execution/configuration contract](local-events-v4.md); retention benefit is calibrated separately, without automatic upgrades |

Disabling all three continuous/1 operators matches frozen baseline witnesses. Disabling only some /3 mechanisms is an ablation, not an exact old kernel. Engineering acceptance does not establish AGI gains. The independent LIF candidate deliberately differs in inhibition, forgetting, structure retention and lifecycle; consult the [continuous](plans/candidate-mechanisms.md) and [LIF](plans/lif-candidate.md) specifications. Do not pool different physical quantities under the same activation heading.

Basic, advanced and JSON modes share configuration. Switching physical model resets kernel parameters; baseline/continuous switching retains common fields. Mechanism groups expose units, defaults, disabling semantics and immutable fields. Display performance settings do not alter scientific parameters. Desktop navigation is grouped; narrow screens get a text navigation menu. Existing conversation, passive and temporal readouts, media and organ controls remain.

LIF Dynamics provides paginated physical states and actual spike timestamps/nodes, with JSON export. `record_spikes` defaults on and affects evidence only. Spike recording is independent of the original 100 ms reader/display sampling, which can miss brief spikes. Single-consciousness spike buffers trigger an early commit near 4 MiB. Shared warmup or a population advance slice exceeding 64 MiB of spike records fails explicitly; reduce scale or revise the recording protocol rather than silently losing events.

## Optional local Transformer

This is an **external research tool**. Core imports no PyTorch and needs no network, pretrained model, CUDA or comparator to operate.

The Local Transformer tab accepts complete integer category sequences, one per line, such as `1 2 3` and `4 5 6`. These IDs belong to the comparator vocabulary, not ThreeMind node identity. Existing text sensory mapping and NFKC normalization remain unchanged.

Optional held-out sequences, vocabulary, depth, width, steps and wall time are configurable. Exact training/evaluation duplicates are rejected; this does not establish absence of more subtle leakage. After training, query the **entire next-event probability distribution**. The view displays the first 16 ranked entries; export retains all entries. No natural-language answer is generated or automatically fed into Core.

Protocols, corpus hashes, losses, accuracy, resource usage and model hashes are stored as project evidence. Numeric `.tmt` artifacts contain a JSON manifest and NumPy arrays in ZIP, not executable pickle. They are distinct from consciousness `.tmind` models.

Explicit optional feedback is available below a probability result: select the receiving consciousness, first channel and intensity, then send once. Every vocabulary slot maps to its declared consecutive channel; no semantic filtering is applied. Ordinary bus admission and source policies apply. Model, request, mapping and intensity provenance are retained. Assisted behavior must not be attributed entirely to ThreeMind Core.

The comparator uses causally masked self-attention, position vectors, feed-forward layers, residual paths and layer normalization, trained by next-event cross entropy. Sources: [Attention Is All You Need](https://arxiv.org/abs/1706.03762), [PyTorch TransformerEncoder](https://docs.pytorch.org/docs/2.14/generated/torch.nn.TransformerEncoder.html). End-to-end backpropagation belongs to this comparator, not ThreeMind's local plasticity rules.

Limits: vocabulary 4096, context 128, width 128, 3 layers and 8 heads; total training/evaluation corpus ≤200,000 tokens. Defaults are 2 CPU threads, 2 GiB process memory, 200 steps and 30 seconds; maxima are 5000 steps, 300 seconds and 4 GiB. Memory/time checks occur between operations, not in an OS sandbox. One tensor operation can cross a check boundary. Lab additionally times out the child; forced timeout need not preserve a model that has not yet serialized. Ordinary budget stops preserve completed work and report the stop reason.

```powershell
$py = '.\.work\kernel-venv\Scripts\python.exe'
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& $py -m threemind_transformer.cli train protocol.json --output comparator.tmt
& $py -m threemind_transformer.cli predict comparator.tmt --tokens '[1,2]'
& $py -m threemind_transformer.cli contract
```

Minimal `protocol.json`:

```json
{"architecture":{"vocabulary":8,"context":8,"width":16,"heads":2,"layers":1,"seed":17},"sequences":[[1,2,3],[4,5,6]],"steps":30,"wall_seconds":30,"threads":2,"memory_mib":2048}
```

Existing output files are not overwritten. Lab reuses its task leases, project access controls and artifact store, with no extra database or MQ. Workers without PyTorch do not claim these jobs; inspect task blocking reasons while they wait for a capable worker.

## Optional remote tool, not a distributed brain

```powershell
& $py -m threemind_transformer.cli serve comparator.tmt --host 127.0.0.1 --port 8997
& $py -m threemind_transformer.cli remote http://127.0.0.1:8997/probabilities --tokens '[1,2]' --model-hash <full-SHA256>
```

Non-loopback calls require `--allow-remote`; non-loopback serving requires `THREEMIND_TRANSFORMER_TOKEN`. The client reads that token from the environment, binds model/request hashes and bounds timeout/response size. It sends declared category IDs, not hidden source text or credentials in URLs. Use a TLS reverse proxy for public deployment. The first GUI manages local jobs; remote calls use the CLI/Python API and do not enter Core's solver.

`probability_frame` only prepares a frame and external metadata. A standalone host may submit it explicitly through its InputBus. Lab uses `POST /api/v2/projects/{project}/transformer/predictions/{job}/inputs` with a receiving run, stable request ID, full channel table and intensity. Reuse the request ID after uncertain delivery rather than blindly submitting another input.

## Compiled standalone constructor

Export definition saves trusted operator order, identity and initial parameters, not a trained consciousness. Use ordinary model export for full trained state. Definitions execute no arbitrary scripts; adding physics requires implementation, validation and registration of a new version.

```powershell
& $py -m threemind_kernels.cli validate definition.json
& $py -m threemind_kernels.cli build definition.json --output .work/device-build
.\.work\device-build\threemind-runtime.exe --inspect-definition
```

Building requires Rust, a C++ linker and cached dependencies; offline is the default, with explicit `--allow-download` for initial dependency acquisition. Outputs include the embedded definition and source/binary hashes. Copy to a matching platform: no Python, database or web UI is needed at runtime. Other platforms need their corresponding toolchain; a Windows executable is not universally portable.

Creation rules and kernel identity are fixed, **plasticity is not**. The executable can load a model, accept stimuli, evolve and save modified state, optionally using SQLite. Restoration rejects different kernel identity and preserves saved parameters, fast state and pending traffic. See `threemind-runtime --help` and [deployment](../zh/v2-operations.md).

## Updating this workstation

Stop old workstation/workers, rebuild the native extension/frontend, then run `python -m threemind_lab.cli migrate` with the dedicated migration account. Schema 51 changes task capability matching only, with no old-model conversion or `data/` scan. Consult the implementation record for actual business-database deployment; isolated test acceptance does not imply deployment.

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

System Python 3.13 plus an isolated venv works; Anaconda is unnecessary. Runtime, Lab and the native extension in `.work/kernel-venv` were updated on 2026-09-30. The old `.venv` still references the removed Anaconda installation; use the explicit `-Python` command above on this workstation. Do not copy this environment to other machines. Fresh installations still follow the [.venv operations guide](../zh/v2-operations.md).
