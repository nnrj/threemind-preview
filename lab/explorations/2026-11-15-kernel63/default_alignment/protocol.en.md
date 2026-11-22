# Aligning 6.3 defaults with 6.1: implementation and engineering checks

2026-11-15. This work implements the author's explicit request. It changes defaults and verifies engineering behavior; it does not resume the broader scientific program or retrain historical subjects.

The initial request was to disable local subthreshold expiry, restore inhibitory usage-time updates, and make inhibition use shared synaptic resources. The author made the resource-precheck default conditional on a substantial performance benefit. All controls already exist; no duplicate controls are added.

Before measurement, substantial improvement was set to at least a 20% reduction in the geometric mean of execution times across the registered materials, with no material slowing by more than 20%. Each material has one warmup and five alternating trials. A qualifying result requires five additional independent trials before retaining the precheck default. Otherwise, restore the 6.1 order: release resources before checking the transmitted amount. Report every condition as well as the aggregate.

The native benchmark uses 32 and 128 nodes with sparse or dense initial connections, fixed inputs and timing, and 60 internal seconds. Other controls follow the requested 6.1 settings. Compare 6.1 directly with the compatible 6.3 configuration, and switch only the resource precheck in the paired cost comparison. These are isolated engineering subjects, not scientific independent samples. Outputs remain in ignored `.work/kernel63-default-alignment/`. Trials run serially, retain 5/4/5/25 GiB of commit/RAM/C/E headroom, and have a 120-second worker timeout. No running service is restarted.

Save pre-edit 6.3 states and their subsequent states before changing defaults. Verify Python, native Rust, and standalone restoration against those witnesses. Compare all numerical state, events, and counters at successive boundaries for 6.1 and compatible 6.3, excluding only version identity, definitions, and equivalent configuration metadata. Cover weak and strong stimuli, grouping, order, same-time accumulation, observation, save/restore, and segmented advancement. Test API defaults and standalone creation without a configuration file. Historical source hashes and original evidence remain unchanged.

## Clarification and superseding decision during the same task

The `activation_floor` zeroing rule already existed in 6.1. The expiry option schedules a local settlement for subthreshold positive activity; it does not remove the existing quiet period. It can nevertheless change when the individual enters quiescence and dies. The lifecycle field describes the whole individual; structural deletion of a node is a separate rule.

After this clarification, the author explicitly requested keeping expiry enabled. The final default therefore retains `subthreshold_expiry_enabled=True`. The other requested changes remain. The initial instruction above is preserved as decision history.

Compatibility checks explicitly disable expiry to reproduce 6.1. Actual-default checks separately demonstrate the remaining expiry-related lifecycle difference. The first cost comparison used expiry disabled; the same precheck comparison is repeated with expiry enabled for the final decision. Neither the zeroing threshold nor the quiet period is changed.
