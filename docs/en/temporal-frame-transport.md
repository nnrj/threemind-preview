# Temporal Frame Transport and Flow Control

[中文](../zh/temporal-frame-transport.md) | [English](temporal-frame-transport.md)

## Why this exists

A carrier is not necessarily a single cognitive event. A long text, a future
audio buffer, or a burst from a remote sensor has internal order. Treating all
of it as one `SensoryFrame` falsely makes every encoded feature co-active in
the same runtime transition. In a literal-character experiment this can create
a near-complete directed graph in one step; that is a transport artefact, not
evidence of a learned association.

ThreeMind therefore preserves the carrier record while delivering its encoded
form as a sequence of causal frames. This is not a semantic length limit and
does not drop or summarise input.

## Input transport

```text
external carrier
  -> adapter encodes an ordered SensoryFrame stream
  -> InputBus envelope + durable queue
  -> scheduled environmental epoch
  -> one Core transition per frame, in sequence order
```

Each accepted carrier receives an `envelope_id`. The original carrier is kept
once in the external stimulus log, together with its source, adapter, frame
count, and delivery state. Every later frame-delivery event records its
envelope, frame index, scheduled epoch, sequence number, and feature count.
This provides an auditable answer to: *what arrived, how was it framed, and in
what order did the runtime receive it?*

The queue state is stored in the model package state. Saving a package while a
carrier is in transit preserves the undelivered frames; resuming the package
continues their ordered delivery.

`GET /api/input-queue` exposes the active runtime's queue epoch, pending-frame
count, and next scheduled envelope without exposing carrier content. The same
view is available per hydrated instance at
`GET /api/consciousnesses/{consciousness_id}/input-queue`.
The Observe panel also shows the current pending-frame count and input epoch
while a carrier is in transit.

### Text sensor defaults

The built-in text sensor exposes two adapter settings:

- **Characters per causal frame** — default `24` normalized characters.
- **Environmental epochs between frames** — default `1`.

They determine temporal resolution, not how much text is accepted. A carrier
of any length is retained and all of its fragments enter the queue. Reducing
the frame width makes local co-activation more fine-grained; increasing it is
an explicit experimental choice that makes a wider sensory moment.

The offline CLI uses the same route. For example:

```powershell
python -m threemind stimulate .\experiment.tmind "a long carrier" `
  --frame-characters 24 --inter-frame-epochs 1 --step 1
```

`stimulate` delivers every causal frame before it saves the package; `--step`
adds settling epochs only after the complete stream. It never silently clips a
long carrier.

Ambient, body-filtered, interoceptive, AI, manual, and remote sensory frames
all use the same queue. Frames due in the same environmental epoch are still
advanced one by one in stable global insertion order; they are never merged.

## Output transport

The runtime's `OutputBus` remains a complete anonymous observation boundary.
The browser transport is a separate application concern:

1. A live WebSocket snapshot is sent as `snapshot_begin`, ordered node/edge
   chunks, and `snapshot_end`.
2. The UI acknowledges each snapshot part after storing it.
3. Live activity uses compact deltas. If a slow client falls behind, the
   transport marks the stream `resync_required` and sends a new complete
   chunked snapshot instead of silently leaving the client with a partial
   topology.

Chunk size only bounds an individual wire message. It is not a graph,
activation, propagation, or memory limit; every node and edge remains part of
the complete projection.

## Consequences for experiments

- Compare experiments at the same adapter framing settings.
- Treat a large one-step graph burst from a legacy unframed carrier as a
  protocol confound, not an association result.
- Inspect the stimulus and frame-delivery logs whenever relating a structural
  event to a carrier.
- For a future image/audio adapter, define its temporal segmentation in the
  adapter rather than inserting arbitrary batching into Core.

The mechanism is intentionally similar to framed transport in networks, but
it is not a network protocol disguised as cognition. Its purpose is to retain
the time structure that an external sensory source already has before the
associative dynamics begin.
