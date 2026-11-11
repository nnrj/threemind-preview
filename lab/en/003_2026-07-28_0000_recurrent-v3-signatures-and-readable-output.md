# 003 — Recurrent V3 Activation Signatures and Readable Passive Output

[中文](../zh/003_2026-07-28_0000_V3重复激活签名与可读输出.md) | [English](003_2026-07-28_0000_recurrent-v3-signatures-and-readable-output.md)

**Date:** 2026-07-28  
**Status:** preliminary observation plus instrumentation audit; controlled replication pending

## Scope and conditions

This entry records several related observations from recent V3 runs. A
consciousness using the anonymous distributed text carrier received repeated
short textual stimuli while weak background stimulation continued. Passive
output was observed both in anonymous mode and, separately, with display labels
enabled for diagnosis.

The earlier observations that a highly constrained body pathway can make a
small stable topology, and that a fixed field can drive global saturation, are
recorded separately in entries [001](001_2026-07-25_2015_minimal-body-triangle.md)
and [002](002_2026-07-27_0000_sensory-constraints-and-global-saturation.md).

## Observations

1. **Recurring anonymous signatures.** Repeating the same short input, and in
   some runs alternating between two short inputs, repeatedly produced the same
   or a closely related anonymous activation signature in passive output. The
   corresponding graph view showed recurrent activation of an overlapping
   local subset rather than a wholly unrelated subset on each trial.
2. **Small recurrent background structures.** Under background-only periods,
   a small linked subset could alternate in activation and passive output could
   report a repeated anonymous structural signature. A visual alternation is a
   candidate local oscillation under discrete activation/decay dynamics; it is
   not, without a recorded time series and controls, evidence of a code or a
   message.
3. **Readable-looking fragments in a diagnostic mode.** When display labels
   were enabled, passive output sometimes rendered short Chinese-character-like
   fragments with partial overlap with recently supplied text. They could look
   like a rudimentary reply or imitation. At present they must be treated as a
   diagnostic readout trace, not as a verified answer or language production.

## Current implementation audit

The anonymous distributed carrier has a stable per-model sensory seed. The
same external carrier therefore produces the same set of channel pulses before
the graph processes them. Recurrent activation for a repeated stimulus is
therefore expected at least in part: it establishes a repeatable
stimulus-to-receptor condition, rather than showing by itself that the graph
has learned language.

In anonymous mode, graph nodes contain no plaintext character or word. Labels
are external sensory metadata and do not participate in Core topology,
activation, association, consolidation, or forgetting.

There is an important diagnostic limitation. In `labeled-observation` mode,
the current label attachment follows the first UTF-8 byte of a character for
an already-emitted byte channel. Many Chinese characters share that first byte,
so a later character can overwrite an earlier display label on the same
channel. Consequently, a readable fragment from this mode is not yet a
reliable reconstruction of a character sequence. `literal-character` is a
more readable control baseline, but it deliberately uses a different sensory
carrier and should not be treated as equivalent to anonymous distributed
encoding.

## Relation to the working hypothesis

Stimulus-specific recurrence is a necessary kind of result for the ThreeMind
hypothesis: an external condition must be able to revisit a related internal
configuration, and repeated association may then alter that configuration.
The observation is compatible with a stimulus–structure correspondence, but
does not establish semantic grounding, comprehension, intention, a self, or
consciousness.

## Required controls and measurements

1. Record the pre-exposure signature and compare it with signatures after
   repeated exposure; distinguish deterministic sensory encoding from a
   topology change caused by learning.
2. Compare the target input with unrelated controls matched for length, byte
   composition, and presentation frequency.
3. Repeat across fresh consciousnesses, fixed seeds, and permuted sensory
   channel identities. Report activated-node and active-edge overlap, not just
   screenshots or rendered phrases.
4. Test retention after a delay with continuing background stimulation, then
   test decay after the relevant input is withheld.
5. Run the same protocol in anonymous distributed, labeled-observation, and
   literal-character control modes. Keep label-mode results separate from
   topology-only results.
6. For apparent oscillation, save a timestamped activation series and test
   periodicity against shuffled background and independent seeds.

## Interpretation boundary

The observations justify continued measurement of repeatable
stimulus–structure–output relations. They do not justify describing the output
as a reply, speech, thought, a Morse-like code, or evidence of artificial
consciousness without the controls above.
