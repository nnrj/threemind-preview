# 004 — Temporal Framing of Long Textual Stimulation

[中文](../zh/004_2026-07-28_0000_长文本刺激的时间分帧.md) | [English](004_2026-07-28_0000_temporal-framing-of-long-textual-stimulation.md)

**Date:** 2026-07-28  
**Status:** implementation and experimental-method correction; long-run validation pending

## Observation

Submitting a multi-paragraph text through the UI once made the running service
appear unresponsive: graph updates stopped arriving, a new consciousness could
not be opened promptly, and the browser later disconnected. Windows socket and
WebSocket proxy errors appeared after the connection was lost, but they were
treated as secondary symptoms rather than the initial cause.

The comparison with continuous background stimulation is important. Background
frames already arrive as an ordered sequence over time. A long text supplied as
one UI action must not be reinterpreted as an instantaneous simultaneous
activation of every constituent sensory pulse.

## Proximate cause and correction

The input path had insufficient temporal framing and back-pressure for a large
text carrier. One request could cause too much work to be scheduled in one
turn, and the resulting graph/output activity could starve normal API and UI
updates.

The input path was consequently organized around an auditable carrier stream:

1. a text carrier is divided into ordered frames;
2. each frame keeps source, sequence, intensity/envelope, and timing metadata;
3. the input bus queues frames in order and advances them across epochs rather
   than silently dropping or reordering them;
4. delivery and output paths apply bounded flow control/back-pressure so a
   slower observer cannot force unbounded work on the running network.

The intent is not to shorten text secretly or replace it with a semantic
summary. It is to represent the temporal structure that was already present in
the external event: a long stimulus takes time to arrive.

## Relation to the working hypothesis

This is a methodological result, not a claimed cognitive phenomenon. It
protects a core premise of the experiment: stimulation is continuous and
ordered, and association should arise from local, temporally situated contact
rather than from an artificial all-at-once batch operation.

It also gives future non-text sensory adapters a common contract. Audio,
images, video, telemetry, or a body signal may be encoded differently, but
their frames need source identity, ordering, timing, and auditable delivery.

## Required validation

1. Send the same long carrier with several frame sizes and inter-frame epoch
   intervals; compare completion time, queue depth, API responsiveness, graph
   statistics, and passive-output history.
2. Verify that all frames appear in the stimulus log in order, with neither
   silent truncation nor duplicate delivery.
3. Compare a framed presentation with a deliberately simultaneous control
   only in a bounded test environment; report differences in activation,
   plasticity, and stability.
4. Test slow or disconnected observers to ensure output flow control protects
   the runtime without altering Core topology rules.
5. Repeat after restart and forced interruption, using persisted history to
   distinguish a delivery failure from a viewing failure.

## Interpretation boundary

Framing prevents an implementation artifact from being mistaken for an
internal collapse or a property of consciousness. It does not by itself make a
long-text response meaningful, and it should be evaluated as part of the
experimental apparatus.
