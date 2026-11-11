# Local activity expression adapter

[Chinese](../../zh/reference/graph-expression.md) · [E50 registration](../../../lab/explorations/2026-10-05-graph-expression/design.en.md)

An optional `threemind_transformer` peripheral, preserving Core, input mapping, the fixed-layout expression model and `graph-expression/1`. Version `/2` is trained from scratch to translate measured anonymous activity over time into bytes. It has no pretrained semantics or cross-window dialogue cache.

## Default observation

`local` first examines the raw window, then retains participating nodes: nonzero activation/arrival flow or an observed rise in inhibition. It preserves activation, inhibition, direct and associative arrivals, generated and pending inhibition, plus actual timestamps. Weak participation is not removed by a ranking cutoff; later zeros remain. Seventeen existing samples are selected by default, without invented interpolation.

Dormant structural storage and purely decaying inhibition without other participation stay in the raw evidence but are not primary expression inputs. No object names, answers, task identities, baseline subtraction or per-query amplitude normalization are supplied. Default local reading omits edges; explicit `graph` input permits an offline structural comparison, not an automatic production route.

Channels retain their original 32-bit anonymous identities. Local node IDs index edges only. New nodes are supported and node order carries no word label. `/2` internally uses a fixed, invertible signed `log1p` representation to handle measurement ranges; raw protocol values and Core outputs are unchanged. This numerical representation belongs to the peripheral network, not stimulus modification.

## Python and JSONL CLI

```python
from threemind_transformer.local_activity import local_process, FIELDS
from threemind_transformer.graph_expression import GraphExpressionConfig, load

config = GraphExpressionConfig(node_fields=FIELDS, use_edges=False)
prepared = local_process(raw)  # start_us/end_us/trajectory from RawActivityStream
model, manifest = load("expression.safetensors", "cpu")
print(model.decode([prepared]))
```

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_transformer.graph_expression_cli config
& $py -m threemind_transformer.graph_expression_cli prepare --input raw.jsonl --output local.jsonl
& $py -m threemind_transformer.graph_expression_cli train --input teaching.jsonl --output expression.safetensors
& $py -m threemind_transformer.graph_expression_cli decode --input probes.jsonl --checkpoint expression.safetensors --output words.jsonl
```

Each line has `id` (optional external receipt) and `process`; training may also contain `text`. Inference rejects teaching labels. IDs are returned, never fed to the network. Default `--view local` accepts raw windows. `prepare` writes the prepared local protocol; consume it with `--view prepared-local`. Only explicit `--view graph` accepts a full graph. Checkpoint fields must match; historical files are not silently upgraded.

Continue training with `train --checkpoint old.safetensors --output new.safetensors`. Existing files are never overwritten. `--device auto` falls back to CPU if CUDA is unavailable; `--device cpu` forces it. External supervised labels do not themselves prove Core semantics: reversal, identical current inputs with different histories, selective silencing/rescue and transfer are still needed.

## Bounds

- 256 MiB input; 128 training or 512 decoding rows. Defaults: at most 32 frames and 512 nodes/frame; overflow is rejected rather than silently truncated. Configurable dimensions remain bounded.
- Default 4000 steps and one hour; explicit wall limit up to four hours. Process RSS 4 GiB, CUDA tensors 3 GiB, at least 2 GiB free system memory. Training accuracy/loss select checkpoints, never test accuracy.
- A finite-vocabulary output without a cue is not automatically an inner monologue. Successful calibration need not generalize to a new experience or a later state.
- Observation frames differ from actual transmitted signals. The copied output bus does not erase this distinction; a signal-only comparison remains pending. [Audit](../../../lab/explorations/2026-10-05-graph-expression/bus-audit.en.md)
- Python/CLI tooling and readable project evidence are delivered; the experimental reader does not silently replace production chat defaults.
