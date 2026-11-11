# ThreeJSON Visualization Boundary

[中文](../zh/threejson-visualization-boundary.md) | [English](threejson-visualization-boundary.md)

## Purpose

ThreeMind uses ThreeJSON as a UI-side scene-runtime foundation for the
consciousness graph. This integration improves rendering throughput and
runtime object management without moving any consciousness rule, model
package rule, or persistence rule into the browser.

The renderer is an observer. It cannot create, strengthen, weaken, delete, or
interpret a Core node or edge.

## Boundary

```text
ThreeMind Core
  -> OutputBus / WebSocket graph snapshots and deltas
  -> UI GraphProjectionStore
  -> ThreeMindGraph visual domain on the ThreeJSON runtime
  -> Three.js GPU scene and canvas
```

The Core publishes only ThreeMind-domain fields: nodes, edges, activation,
stability, touch markers, spatial coordinates, removals, and lifecycle
metrics. The UI projection store is responsible for merging those messages.
The visual domain maps the merged view to GPU resources.

There is no reverse dependency from Core to ThreeJSON. Core code does not
import ThreeJSON, and a `.tmind` model package contains no ThreeJSON IDs,
geometry objects, shader state, or browser-only metadata.

## Runtime projection

The UI keeps two deliberately separate representations:

- **GraphProjectionStore**: a mutable, UI-local projection indexed by node and
  edge ID. It applies a full snapshot once and then merges incremental deltas.
- **ThreeMindGraph domain**: a dedicated presentation domain that owns only
  visual handles such as `threemind:node:42` and
  `threemind:edge:42:75`. These are ThreeJSON runtime entity identifiers, not
  Core node identifiers and not persistent model data.

WebSocket changes update this store immediately. React receives a coalesced
snapshot at animation-frame cadence for counters and panels, while the graph
domain receives the exact delta directly. This avoids rebuilding the whole
graph through React for each activation event.

## GPU update model

The graph domain uses ThreeJSON dynamic point and segment batches. A changed
node updates its own point slot and the slots of its incident segments; removed
entities release only their own slots. A frame-commit scheduler merges those
dirty ranges and uploads them to the GPU on the next frame.

This is intentionally different from a full scene rebuild or a full vertex
buffer upload after every Core event. It keeps high-frequency activation and
edge updates local to the visual projection.

The optional display-only motion setting remains a presentation feature. It
does not alter Core coordinates, topology, memory, association, forgetting,
or any recorded experimental state. It is disabled by default.

## Renderer choices and fallback

New UI settings use `threejson` as the default 3D renderer. Existing users can
still explicitly choose:

- **ThreeJSON GPU projection** — the incremental default.
- **Three.js legacy fallback** — the former renderer, retained for comparison
  and recovery.
- **Canvas 2D** — the classic two-dimensional fallback.

Persisted legacy `three` settings are intentionally not silently rewritten.
They continue to select the legacy renderer until the user chooses another
mode.

## Version scope

The initial integration was built against `threejson@0.1.0-alpha.9`,
`@threejson/assets@1.1.3`, and `three@0.184.x`. ThreeMind uses only public
ThreeJSON exports and its own visual domain; it does not import private package
paths.

An optional future ThreeJSON optimization would be a narrow public runtime
entry point containing only the scene runtime, dynamic batches, commit
scheduler, and runtime entity registry. That would reduce the lazy graph
renderer chunk, but is not required for correctness of this integration.
