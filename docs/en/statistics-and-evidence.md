# Statistics, Evidence, and Research-Data Export

[中文](../zh/statistics-and-evidence.md) | [English](statistics-and-evidence.md)

ThreeMind's **Statistics & Evidence** module is a read-only measurement layer outside Core. It may consume durable history and anonymous observations already published by the OutputBus, but it must not write stimuli, labels, edges, or interpretations into the network. Neither a statistical result nor a canvas animation may feed back into dynamics.

## Measurement objects

Four identities must remain distinct for recurrent structures:

- `state_signature`: a quantized instantaneous activation, stability, and touch state. It describes a cross-section, not graph identity.
- `structure_id`: exact node-ID set plus induced directed-edge set. The structure may retain this identity across different activation states.
- `topology_class_id`: an identity-free topology candidate class. It helps group similar structures but is not a proof of graph isomorphism.
- `occurrence_id`: one occurrence of a structure at one tick. An observation and its later alert count once when they share this identity.

Detection freezes an anonymous subgraph containing the node state and internal directed edges, weights, and stability at that tick. Readable labels are stored beside this evidence as external annotations. They are not semantic Core properties and do not contribute to structural identity.

## Statistics page

The title-bar **Statistics & Evidence** page provides:

1. Run overview: counts of stimuli, events, readouts, temporal windows, and dynamics records, plus stimulus-source distribution.
2. Dynamics curves: node and edge counts, total activation and inhibition, creation, removal, direct touch, and associative touch.
3. Recurrent-structure catalogue: occurrence count, first/latest tick, source proportions, state signatures, and frozen subgraph.
4. Temporal-window readouts: convergence, oscillation, decay and transient classifications plus ranked nodes, with on-demand per-tick activation curves for ranked nodes inside each window.
5. Paired ablation: matched control and intervention isolates derived from one captured source state.

Per-tick curves exist only if detailed dynamics tracing was enabled before the experiment. An absent trace is missing data. It must not be silently filled with zeros, interpolated as raw evidence, or reconstructed from the current snapshot as if it were historical observation.

## Evidence dataset

**Export evidence data** produces a ZIP with SHA-256 checksums. It contains:

- `manifest.json`: dataset schema, consciousness identity, creation time, and history origin;
- `records/*.jsonl`: raw stimuli, events, observations, AI interpretations, and dynamics trace;
- `tables/*.csv`: recurrent structures, temporal readouts, and dynamics analysis tables;
- `subgraphs/*.json`: frozen anonymous subgraphs plus external label annotations;
- `data_dictionary.csv`: field definitions;
- `checksums.sha256`: integrity digest for every enclosed evidence file.

JSON Lines is the fidelity-preserving primary record; CSV supports statistics software and manual review. CSV is UTF-8 with BOM and JSON is UTF-8. A spreadsheet may be a viewing tool, but should not be the only raw-data format.

## Interpretation discipline

- Structural recurrence is not semantic recurrence; a topology candidate class is not strict isomorphism.
- Readable labels are instrumentation; anonymous identities remain the primary evidence.
- AI may summarize exported records but must not replace structural detection, temporal classification, or statistical testing.
- Exploratory threshold tuning must be separated from confirmation. Confirmatory runs should preregister code version, parameters, seed, stimulus schedule, primary outcomes, and exclusion rules.
- Every manuscript figure should be traceable to an evidence ZIP, model-package digest, and code revision.
