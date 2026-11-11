# Research operations, snapshots and compute devices

[中文](../zh/v2-research-tools.md) · [Implementation plan](plans/research-tooling-and-candidate-experiments.md)

## UI entry points

- **Settings → Compute tools and Agent interfaces**: worker-reported capabilities, defaults for new Transformer tasks, operation schemas and MCP configuration. Existing consciousnesses and protocols keep their settings.
- **Consciousness → Research operations → Plans → Repeated-stage experiment**: repeat each stage's ordered steps before moving on. GUI and JSON share `research-plan/3`; anonymous frames use the ordinary input bus. Existing `/2` protocols and hashes are preserved.
- **Models and evidence → Experiment snapshots**: pause the consciousness and plans before saving. Optionally include your notes, reports and completed tool artifacts. Temporal readouts are the default preview. Import creates an archive only; explicit restoration creates a new paused consciousness.
- **Settings → Storage audit**: inspect metadata, upload occupancy and restoration references without reading old large payloads or deleting data. Missing references do not prove safety. Actual cleanup still requires full preview and human confirmation.

Unavailable/lost WebGL2 falls back to Canvas 2D with the existing display sample, layout, node selection and PNG export. WebGL can be retried. No 3D view is available during fallback; Core computation is unchanged. Display budgets remain configurable, but software rendering may be slower for large graphs.

Report previews support current-project note images and evidence-artifact download links. They do not automatically fetch arbitrary remote images or another project's private attachments; public shares do not inherit private access. Images inside Markdown commentary currently appear in platform previews only. HTML/Word/PDF exports embed native data charts rather than those attachments; this study's overview PNG is also included in its raw evidence archive and source documentation.

## CLI, agents and MCP

The catalog comes from the live service's OpenAPI. UI, CLI and MCP share authorization, revision and business validation. Core requires neither the optional MCP SDK nor an LLM.

```powershell
$py = '.\.work\kernel-venv\Scripts\python.exe'
& $py -m threemind_lab.cli ops list
& $py -m threemind_lab.cli ops show bundle.export
& $py -m threemind_lab.cli ops preflight bundle.export --arguments request.json --request-id <UUID>
& $py -m threemind_lab.cli ops call bundle.export --arguments request.json --request-id <same-UUID>
& $py -m threemind_lab.cli ops receipt --project <project-UUID> --request-id <same-UUID>
& $py -m threemind_lab.mcp_server
```

The UTF-8 file contains `path`, `query` and `body`; consult `ops show` for fields. Preflight validates schema only, not current permissions, revisions or budgets. `experiment` aliases `ops`. Reusing `X-ThreeMind-Request-ID` replays completed receipts. **Business commits and generic receipts are not atomic**: a crash between them can leave pending/unknown results. Reconcile with jobs/objects instead of retrying under a fresh ID. Error responses also belong to their ID; corrected arguments need a new ID. Advances and stage commands additionally persist absolute targets, cursors and step receipts without repeating completed teaching.

Six MCP tools expose catalog, schema, preflight, call, receipt and restricted bundle file exchange. Cleanup and account/credential administration remain human-controlled. The host supplies `THREEMIND_API_URL`, `THREEMIND_API_USERNAME`, `THREEMIND_API_PASSWORD`; credentials are not model-generated arguments. File exchange requires `THREEMIND_MCP_TRANSFER_DIR` and verified archives within that directory. Arbitrary files are not exposed by default.

## Experiment bundles

`.tmind` holds Core numeric state; `.tmt` holds independent Transformer weights; `.tmexperiment` holds context and evidence. None is repeatedly rewritten during ordinary execution.

`threemind.experiment-bundle/1` uses ZIP64, 4 MiB content-addressed blocks, SHA-256 and compression. It contains Core/runtime state, in-flight inputs, sensory/readout context, random state, original media, stages and repetition cursors. Optional notes/reports include versions and source references. Limits: 8 GiB compressed, 20 GiB logical expansion, 4096 entries, 32768 chunks, 15 GiB free temporary disk. `THREEMIND_SCRATCH_DIR` overrides `.work/bundle-temp`.

Import checks names, sizes and hashes without extracting arbitrary paths or executing code. Restoration revalidates state, implementation/dependency identity, protocols and commands. Unsupported versions remain read-only. Numeric state and clocks are retained; experiment/envelope identities and project ownership change, not channels or carrier contents. Live telemetry changes require acknowledgment. Device credentials and automatic reconnection are excluded; dead consciousnesses cannot be revived.

One bundle covers one committed consciousness boundary. Population, ecology, frozen-study and assessment individuals can be archived but do not restore their complete coordinators. Uncommitted operations, active capture, pending live-device blocks or unsupported commands block continuation. Transformer artifacts cover completed tasks, not in-progress optimizer continuation. Strict code/dependency fingerprints may make an older bundle read-only after a tool upgrade; no approximate restoration occurs silently. Large previews currently spool and verify the archive, so their cost scales with package size.

```powershell
& $py -m threemind_lab.cli bundle download --project <UUID> --bundle <UUID> --file experiment.tmexperiment
& $py -m threemind_lab.cli bundle upload --project <UUID> --file experiment.tmexperiment --request-id <UUID>
& $py -m threemind_lab.cli bundle copy --project <source-UUID> --bundle <UUID> --target-url https://your-service.example --target-project <destination-UUID> --request-id <UUID>
```

Files never overwrite evidence; uploads reuse verified chunks. Browser retries reuse a locally saved ID. When persistent browser storage is disabled, use a stable CLI request ID for continuation across reloads. Peer copies also create read-only archives.

Optional OCI uses the separate [ORAS CLI](https://oras.land/docs/commands/oras_push/) and local `oras login` credentials:

```powershell
& $py -m threemind_lab.cli bundle push-oci --file experiment.tmexperiment --reference registry.example/research/run:trial-1
& $py -m threemind_lab.cli bundle pull-oci --file received.tmexperiment --reference registry.example/research/run@sha256:<digest>
```

This transports a single data layer, not an executable container. Pull checks OCI and inner hashes; push freezes a copy and verifies the remote manifest. Local archives, mocked registry exchanges and bounded subprocesses are tested; a real registry round trip remains unverified.

## Device policy and validation boundaries

Protocol defaults stay `cpu`; new GUI drafts default to `auto`. Automatic CUDA requires three representative paired measurements, including transfer costs, all showing at least 20% speedup and enough VRAM. Explicit `cuda` overrides the speed advice, but insufficient resources or recognized GPU failure still produce recorded fallback. A GPU failure can restart once in a fresh CPU child from identical initial conditions within the remaining budget. Both attempts are retained; partial trajectories are never spliced.

Defaults: 2048 MiB GPU budget, 512 MiB reserve, one GPU tool job, FP32, TF32 disabled. These are allocation/monitoring budgets rather than operating-system isolation. Evidence records actual device, Torch/CUDA/driver, timing, failure and fallback. Optional tools are isolated from Core; all three consciousness kernels continue on CPU.

```powershell
& $py -m threemind_lab.cli compute
& $py -m threemind_transformer.cli predict model.tmt --tokens '[1,2]' --compute-device auto --gpu-memory-mib 2048
```

The probability service preserves its seven-field contract. `/compute` separately exposes the latest execution evidence. This machine currently uses CPU-only Torch; real GPU speed, VRAM peak and numerical consistency await CUDA configuration.

Data, temporary directories, models and bundles are ignored by Git. `python scripts/check-git-data.py` checks staged file types and a 10 MiB per-file limit without scanning old data or changing history. Commit source, designs, summaries and evidence locators; keep large evidence in the database or verified bundles.
