# 004 — Innate Models and Developmental Training

[中文](../zh/004_先天模型与发育训练设想.md) | [English](004_innate-model-and-developmental-training.md)

## Proposal

A future controlled 3D environment could expose an initially anonymous, plastic network to continuous visual, auditory, bodily, action-consequence, and host-physical signals. After one developmental run or multiple selected generations, its connection state could be preserved as an “innate model” from which several later individuals continue under different environments.

“Innate” must not mean writing words, object categories, reward, survival, or named brain regions into nodes, nor inserting a pretrained external neural network into Core. It only means that an instance starts from inherited connections, plasticity state, and sensory mapping produced under a declared environment and sensorium rather than from an empty graph. This is a testable engineering analogy, not an assertion of biological equivalence.

## Variables that must remain separable

- empty initial model versus inherited model;
- identical senses with different environmental histories;
- identical environment with different sensory resolution or cadence;
- naturally differentiated local function versus a forced region rule;
- individual learning, cross-generation selection, and researcher snapshot selection;
- plastic inherited tendencies versus nearly immutable consolidation.

Every innate package should retain its source experiment, ancestor checksums, sensory and spatial configuration, training carriers, seed policy, selection criterion, snapshot time, and later mutations. Without this provenance, emergence cannot be distinguished from adapter bias or researcher selection.

## Current decision

The current milestone implements audio/visual sensation and anonymous output organs only. It adds neither a pretraining pipeline nor forced regions. Multimodal adapters naturally use different physical features and anonymous namespaces, but Core does not read “auditory” or “visual” names to create regions. A developmental environment and lineage manager should remain a later, independent experiment module after single-consciousness dynamics, audit, and controls are stable.
