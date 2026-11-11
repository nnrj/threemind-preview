# ThreeMind Architecture Boundaries

[中文](../zh/architecture-boundaries.md) | [English](architecture-boundaries.md)

## Purpose

ThreeMind is an experiment in continuous, plastic associative dynamics, pursued
toward the ultimate objective of artificial consciousness. The current graph
does not claim to have achieved that objective. The experiment separates the
changing network from the carriers, observers, and applications around it so a
result can be inspected without silently adding meanings to node state.

## Input boundary

```text
environment source / tool / remote device
  -> sensory and body adapters
  -> anonymous SensoryFrame
  -> InputBus queue
  -> transparent gate (or an explicitly enabled environmental selector)
  -> associative runtime
```

`SensoryFrame` is the final input protocol. It contains anonymous numeric
channels, intensity, and source metadata. Text, pixels, sound, tool output,
and future smell encodings belong to adapters. Their readable carrier may be
kept in external logs, but anonymous Core nodes never store it.

The InputBus is temporal rather than a bulk accumulator. An adapter may emit a
stream of frames for one carrier; the host assigns an audit envelope and
delivers each frame in causal order as a separate runtime transition. See
[Temporal Frame Transport and Flow Control](temporal-frame-transport.md) for
the framing, queue persistence, and browser flow-control protocol.

An adapter already limits information because it samples, encodes, and omits
most of its source. This is different from the Core gate. The default gate is
transparent: every adapter-encoded channel reaches the associative runtime
without a Core-side relevance, novelty, or deterministic channel-bias score.
The raw frame intensity remains the stimulus intensity; any later internal
consolidation value is not renamed or presented as stimulus strength.

An environmental selector can be explicitly enabled when an experiment needs a
finite-throughput body constraint. It is not a default cognitive tendency.
Core has no implicit propagation, edge-adaptation, node, or edge budget:
any such limit must be explicitly present in the model package.

### Immutable V3 sensory modes

V3 chooses its sensory encoding and annotation policy when a consciousness package is
created; it cannot be switched on a populated instance, restored snapshot, or
clone. Graph nodes remain anonymous in every V3 mode; the package records
`sensory_encoding` and an external annotation table:

- `anonymous-distributed` is the standard V3 model.
- `labeled-observation` emits exactly the same distributed
  numeric frame as the anonymous mode, but attaches display-only labels to
  existing channels. With the same seed and frames, its graph dynamics must be
  identical.
- `literal-character` maps each normalized text character to a
  stable readable sensory channel. It is an intentionally different,
  interpretable experimental baseline, useful for validating stimulus-response
  and readout mechanisms; it is not the standard anonymous consciousness mode.

Labels are stored in the external package annotation table and read by a
character driver. They never take part in activation, propagation, edge formation,
consolidation, forgetting, or attention selection.

## Body adapter

The ambient source exists independently of the body. The built-in simulated
body receives that raw field and performs sampling, thresholding, sensory
adaptation, and noise before a filtered anonymous frame is queued. It has no
semantic preference and does not manufacture the environment. An optional
interoceptive adapter is a separate, explicitly enabled internal-body source.

## Physical telemetry sensory boundary

`host-telemetry-field` is a default-on application-layer sensory adapter. One
shared collector observes read-only host CPU, memory, disk, aggregate network,
and power counters in monotonic wall time, then each consciousness maps that
sample with its own sensory seed. `process-telemetry-field` observes the whole
ThreeMind service process. `runtime-telemetry-field` instead measures real
thread CPU and wall-clock timing around one consciousness's Core epochs and
feeds it back no earlier than a later input epoch. Both feedback devices are
off by default. All three enter only through `SensoryFrame` and `InputBus`; none
is Core energy, a graph-edit route, or an OutputBus echo. Missing counters remain explicitly unavailable.
See [Physical Telemetry Sensory Adapters](physical-telemetry-sensory-adapters.md).

## Multimodal sensory and output boundary

`auditory-sensor` and `visual-sensor` live outside Core. They turn uploaded
carriers or live browser PCM/image/video samples into framed, anonymous,
non-negative `SensoryFrame` input. Deterministic physical transforms may
resample audio, measure frequency-band energy, grayscale pixels, extract local
edges, apply an explicit threshold, or scan retinal patches. They use no ASR,
OCR, object recognition, pretrained embedding, or language model. Short audio
blocks form complete sensory windows before delivery, while visual patches are
queued in order so one whole image cannot accidentally become a dense
co-activation instruction.

`acoustic-output-organ` and `activation-image-projector` subscribe only to
anonymous OutputBus frames and project node identity/activity into oscillator
controls or grayscale pixels. They never read readable labels and never feed
their result back into InputBus automatically. Uploaded raw carriers use
content-addressed retention; live microphone and camera carriers are ephemeral
by default. See [Multimodal Sensory and Output Adapters](multimodal-sensory-and-output-adapters.md)
for protocols, configuration, audit, and interpretation limits.

## Attention and competition plugins

The runtime exposes a neutral plugin protocol. A plugin must explicitly request
competition before it can rank or discard anonymous channels; a multiplier on
its own cannot silently enable selection. A plugin may only constrain an
anonymous channel's gain or an enabled competition capacity. It must not write
node/edge state, inject text, or issue a goal command.

`energy-budget` is now an independent external resource-supply adapter rather
than an attention modulator. Only a model that explicitly enables energy
simulation consumes the experimental scalar during direct activation,
associative propagation, and optional inhibitory diffusion. Core never
recovers energy internally. The default-off adapter can only supply a configured
finite amount through the resource port; it never ranks or filters stimuli and
never changes attention capacity. This scalar has not been identified with
physical energy and therefore cannot justify survival, reward, or content
preferences.

## Local inhibition, energy, and dynamics observation

The runtime enables topology-local inhibition by default while retaining an
explicit off switch for comparison experiments. Excitatory
edges remain directed; inhibition merely treats an edge in either direction as
physical adjacency and diffuses a finite, decaying, delayed potential between
neighbours. It has no causal-wave identifier, global winner scan, or semantic
goal. The legacy global homeostatic clamp is off by default and rescales total
activation only when a package explicitly enables it. Irreversible energy death, physical telemetry sensation, and detailed dynamics
tracing are independent optional capabilities. See [Local Inhibition, Optional
Energy Accounting, and Dynamics Tracing](local-inhibition-energy-and-dynamics.md)
for the complete rules and interpretation boundary.

## Local novelty, association, and consolidation

Novelty is not an input ranking feature. When a new edge is formed, the runtime
can apply a small, configurable local novelty bonus only if it touches an
already connected neighbourhood *and* receives a non-zero associative touch
from local propagation. Within that positive range, weaker associative touch
is treated as more novel. An isolated edge or a connection with zero
associative touch receives no such bonus. Repeated direct contact and repeated
associative traversal separately strengthen stability and support. These are
carrier-agnostic graph dynamics, not semantic recognition rules.

## Output boundary

```text
associative runtime
  -> anonymous OutputFrame
  -> OutputBus
  -> structural observer / character driver / visualizer / tool sink
```

An `OutputFrame` contains the complete current anonymous node/edge projection,
metrics, and a structural delta. It does not carry node labels or a
pre-decided destination. The passive structural readout is an output adapter;
it no longer needs direct graph access. The optional character driver is a
separate adapter, useful only when an external V1 symbol dictionary exists.

Complete output and transport output are separate concerns. The live browser
connection receives acknowledged snapshot chunks plus deltas; when it falls
behind, it is resynchronised from a complete projection rather than silently
left with a partial graph.

Output is not automatically fed back as input. A future self-feedback
experiment should route a bodily/environmental consequence through a separate
adapter with delay, distortion, noise, and an explicit switch.

## Network transport boundary

Network transport is not part of either bus. It is an application/edge adapter
that authenticates, validates, serializes, and forwards anonymous frames.

The implemented protocol is `threemind-network/1` over WebSocket:

1. Connect to `/api/network/input` or `/api/network/output`.
2. Send a `hello` envelope with protocol, peer ID, and shared token.
3. Input peers may send `sensory_frame` envelopes with anonymous channels.
4. If explicitly enabled, they may send `modulation_frame` envelopes with only
   scalar `gain` and `budget` values.
5. Output peers receive anonymous `output_frame` envelopes.

The shared token is stored encrypted locally and is never returned by the API.
Network transport is disabled by default. For non-loopback deployments, use a
TLS reverse proxy and treat the network token as a deployment secret.

`modulation_frame` is deliberately analogous to a remote physiological signal,
not an administrator command. It cannot create nodes, edit edges, submit text,
or select a particular concept.

Example input handshake and frame:

```json
{"protocol":"threemind-network/1","type":"hello","peer_id":"sensor-a","token":"shared-secret"}
{"protocol":"threemind-network/1","type":"sensory_frame","consciousness_id":"optional-id","channels":{"0":0.42,"17":-0.10},"intensity":0.8}
```

An allowed modulation frame has no channel or graph fields:

```json
{"protocol":"threemind-network/1","type":"modulation_frame","gain":0.85,"budget":0.70}
```

An output subscription receives `output_frame` envelopes containing metrics,
anonymous node IDs/activities, anonymous edges, and the latest structural
delta. Remote channel identifiers are keyed into each local consciousness's
sensory mapping; they never become Core labels.

## Design consequences

- Function-like regions should be allowed to emerge from repeated sensory
  activity and connectivity rather than being predeclared as brain regions.
- Different consciousnesses may form different internal mappings for similar
  external carriers.
- Readable output is an adapter interpretation, not evidence that Core holds
  words or meanings.
- UI and CLI are management-plane clients. They configure adapters and inspect
  logs; they do not implement associative dynamics.

### 2026-10-05：中枢适配器 / Central adapters

[面向任务的功能分类与边界 / Task-facing roles and boundaries](reference/central-adapters.md)。协议和Core权限不因名称改变；不是预设脑区。 / The name changes neither protocol nor Core privileges and creates no predefined brain region.
