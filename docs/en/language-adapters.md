# Language senses and external Transformers

[简体中文](../zh/language-adapters.md) · [Approved plan](plans/robotics-and-language.md)

Language can pass through an optional Transformer sense into ThreeMind, and actual Core activity can pass through an optional Transformer into text. These are peripherals. Core equations, learning rules and anonymous channels remain unchanged.

## Independent input and output choices

Input may use the existing text sensor, Qwen3-Embedding-0.6B, or a byte-level Transformer initialized from random weights. Output may remain raw activity or use Qwen3-0.6B or a separate byte-level Transformer. A scratch input with raw output needs no decoder.

The scratch model uses UTF-8 bytes plus two boundary symbols, with default width 128, four attention heads, two layers and a 512-byte context. It has neither pretrained weights nor a learned tokenizer. Seeds reproduce initialization. Training uses only supplied examples. Initial output may be unreadable; that says nothing by itself about Core activity or language understanding.

Input vectors use a fixed dimensional basis, L2 normalization and signed anonymous channels through the existing bus, without choosing destinations by reading the graph. The original text route keeps its normalization, framing and mapping. Output stores a bounded activity trajectory, then applies time bins and anonymous projection. Original passive/temporal readouts and complete trajectories remain available; projection cancellation is not absence of activity.

## Strict conversion and external assistance

A strict decoder runs in a separate process and receives only declared activity features, frozen conversion weights and a constant scaffold. It cannot see the incoming question, lessons or answers. Qwen still contains pretrained language knowledge: information isolation prevents direct leakage, but does not itself establish that experience resides in Core. Assisted mode explicitly permits the current input text and records this exposure.

Without a calibrated head, strict mode shows actual activity and an uncalibrated status. Calibration pairs measured activity with researcher-supplied text. These are external supervised targets, not evidence of Core understanding. Qwen base weights stay frozen; a scratch output model may explicitly be trained alongside its mapping head.

Scratch input/output models may also learn next-byte prediction from individual sentences. Every training run produces a new safetensors artifact, corpus/parameter digest, parent identity and loss evidence. Existing consciousnesses do not silently acquire new weights. Freeze converters before comparison; use a new consciousness branch to apply a trained version.

## Operation

The Dialogue experiment UI offers creation, independent routes, stimulus submission and visible raw/conversion responses. Training and evidence have separate tabs. This instrument advances simulation by turns, pausing while awaiting input. The response window is not a consciousness lifetime limit; death never triggers automatic revival.

REST uses `/api/v2/projects/{project}/language`. The shared CLI/MCP operation catalogue exposes `language.catalogue/create/send/turns/train_scratch/train_head`. Existing jobs, leases and worker capability matching are reused. Inference never downloads missing model assets.

The Versions and evidence tab exports/imports complete `.tmlanguage` device bundles through `language.export/import`. Bundles include Core, in-flight inputs, readout state, sensory identities, trained scratch weights and the conversion head. Pinned Qwen files are installed separately rather than duplicating 2.6 GiB per snapshot. Imports create a separate paused consciousness, preserving kernel identity and death state. All members and hashes are checked, with a 256 MiB bundle limit. This is device transfer, not a complete research-project archive.

Standalone operation needs no PostgreSQL:

```powershell
$py = ".work/kernel-venv/Scripts/python.exe"
& $py -m threemind_transformer.language_cli template | Set-Content -Encoding utf8 language.json
& $py -m threemind_transformer.language_cli turn --protocol language.json --store language.sqlite --text "A is a pine nut." --output first.json
& $py -m threemind_transformer.language_cli turn --protocol language.json --store language.sqlite --resume --text "B is a bell." --output second.json
& $py -m threemind_transformer.language_cli export --store language.sqlite --output saved.tmlanguage
& $py -m threemind_transformer.language_cli import saved.tmlanguage --store restored.sqlite --assets-dir restored-assets
```

For scratch input, set `input_model` to `scratch`, keeping `output_model` as `raw`. Use a new store or instance ID when changing protocols. `language_cli train training.json --kind scratch --output learned.safetensors` trains a scratch model; `--kind head` trains an output conversion. JSON uses the same `ScratchTraining` / `LanguageTraining` contract as the API. Existing output files cannot be overwritten. SQLite is bounded device recovery, not an indefinite research archive; retain turn evidence separately or use Lab.

For new instances, CLI accepts `--kernel` and `--config`; resumed instances retain their saved configuration. Export trained weights with the applicable `--head`, `--input-checkpoint` and `--output-checkpoint` flags; missing or mismatched identities fail validation. After import, use the protocol and weights written into `restored-assets` for subsequent `turn --resume` calls.

Install Qwen explicitly using `python -m threemind_transformer.language_assets install embedding` and `install decoder`. Roughly 2.6 GiB of pinned, hash-verified files live under `.work/language-models` on the project drive; `THREEMIND_LANGUAGE_MODELS` overrides this location. Scratch requires only Torch and safetensors. CPU is supported. A CUDA device failure retries from the same frozen inputs in a fresh CPU process; invalid data or exhausted budgets are not reported as successful computation.

## Validation status

2026-10-02: unit checks cover scratch initialization/training/restoration, strict information isolation, and text-bus continuation. Actual isolated database/worker and 1440/390 UI acceptance covers creation, sending, training and evidence download. The actual Qwen encoder processed two sentences on this GTX 1650 at about 1.13 GiB peak reserved VRAM. This was an engineering smoke test, not a language-learning result. Arm utility and language attribution experiments remain in the approved plan.

## Source statement, translated from Chinese (2026-10-02)

The user requested a randomly initialized, untrained Transformer connected as a ThreeMind sense or external processing center. Language can travel through Transformer, adapter and input bus into Core. Core responses may optionally pass through a Transformer on their way out. The architecture should support language training and interaction without entering Core; the Transformer adapter is fundamentally another peripheral. The [Chinese edition](../zh/language-adapters.md) retains the original statement.


2026-10-02 addition: actual CUDA encoding, two-step head training and strict decoding completed, at approximately 1.13 / 1.32 / 1.14 GiB peak reserved VRAM. This is engineering acceptance, not language accuracy. The independent `threemind-transformer` package is optional: Runtime alone imports neither Torch, language models nor Lab. Install `packages/transformer[scratch]` or `[language]` when needed.

Same-day verification deliberately limited this isolated job to 128 MiB VRAM, triggering a real allocation failure and successful fresh-process CPU encoding from the original inputs. Windows virtualenv launchers caused earlier RAM undercounting; accounting now includes the owned process tree, measuring about 3.82 GiB peak for CPU encoding. Earlier launcher-only RAM measurements are invalid. Budget termination includes owned descendants and no unrelated processes. Portable restoration preserves the next-input Core state hash; isolated database and UI checks cover import, continued input and export.


E26 scientific pilot completed: both text and random-Transformer input routes reconstruct four calibration words with a scratch output model, but do not reliably express new assignments. Activity intervention affects text; this is not a claim of natural conversation. [Report and limits](../../lab/explorations/2026-10-02-robot-language/report.en.md)

## 2026-10-04: ongoing observation without new input

Dialogue adds **Observe ongoing activity / Stop observing**. Each window advances normally and preserves full activity, existing readouts and optional text. It sends no empty string, artificial question or awakening stimulus. In-flight events still arrive; pending-input counts distinguish no *new* input from no outstanding external arrivals. Death stops observation without revival.

UI calls are bounded at120 windows and CLI calls at256; these are observation-task budgets, not lifetime limits. Stopping finishes the current window and preserves state. Simulated time and computation time appear separately: independently loading Qwen for each interactive window may run slower than real time on this machine. Offline batch comparison reuses frozen weights but never generated tokens or KV history.

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.language_cli observe --store language.sqlite --windows 20 --output activity.jsonl --compute-device cuda
```

Add `--head head.safetensors` for a calibrated converter and `--output-checkpoint` for trained scratch output weights. Restore the saved protocol and Core identity; do not substitute mappings. Save a new SQLite revision and flush JSONL after each window; existing output files cannot be overwritten. Python exposes `LanguageSession.observe()` and `.stream(windows=20)`. REST is `POST .../language/sessions/{run_id}/observations` with `request_id` and `expected_revision`; shared CLI/MCP operation is `language.observe`.

No-input decoding always uses strict exposure: current activity, constant scaffold and frozen converter. Even an assisted session does not forward its previous question; generated text is not fed back. Zero projected activity stays silent; cancellation despite raw activity must still be checked in the complete trace.

Optional `threemind.language-adapter/2` supports `feature_layout="unsigned-peak"`, retaining the activation maximum in each temporal bin/bucket without signed cancellation; bucket collisions remain possible. Legacy `/1` signed averages, serialized fields and mapping identities remain unchanged. A new layout cannot silently reuse an old head. This versions observation, not Core; [E42](plans/scratch-language-centre.md) compares both layouts.

### 2026-10-05：中枢适配器 / Central adapters

[面向任务的功能分类与边界 / Task-facing roles and boundaries](reference/central-adapters.md)。协议和Core权限不因名称改变；不是预设脑区。 / The name changes neither protocol nor Core privileges and creates no predefined brain region.
