# 6.3: simpler connection state and inhibitory distribution

2026-11-15. The author authorized a usage-time switch in 6.2, off by default; a new 6.3 without the weight/resource/learning separation options or their master switch; optional weight-proportional distribution of a source's inhibitory total, with per-connection transmission remaining the default; and prefix verification plus a comparison of the two distribution rules. This is an implementation plan, not a result.

- `inhibition_updates_usage=False` controls only whether successful inhibitory transmission updates `last_pass_us`. Excitatory transmission still updates it. Explicit inhibitory learning and its `last_touch_us` remain governed by their existing rules. Older 6.2 artifacts lacking this field restore with true.
- 6.3 has independent Python/Rust transitions, identity, definition and state. It starts from the reviewed 6.2 code before separation, with subsequent changes checked explicitly. Existing numerical, protocol, resource and storage primitives remain shared.
- `inhibition_distribution="per-connection"` retains current transmission. `"weight-proportional"` divides the source's total among unsilenced, awake outgoing connections in proportion to their effective weights, read at the beginning of this emission. A zero sum sends nothing. Distance, resource release and thresholds apply afterward; failed shares are not redistributed. This does not bypass resources, disable learning or reorder emissions.
- Source inhibitory energy cost uses the distributed total in proportional mode and the sum of per-connection offers in the current mode. Failed offers retain their energy cost. Source inhibition-state subtraction retains its existing rule.
- API, commands, UI, persistence, inheritance and standalone Rust support 6.3. The global creation default stays 6.1. All 6.2 separation options and old evidence remain intact.

Engineering checks cover historical restoration, Python/Rust parity, complete continuity, passive observation and absence of separation fields. Matched 6.2/6.3 per-connection configurations must preserve numerical trajectories. Benchmarks separate implementation cost from altered event counts.

The separately preregistered study tests actual 6.3 defaults, the usage switch and distribution rules on prefix discrimination and sustained activity. Exploratory configurations are not default results. Negative results close normally; there is no unbounded parameter search. Results support a recommendation, not an automatic default change.

Archive verification uses the authorized local research API. Reports, backlog and histories are updated; the main revalidation and manuscript remain paused. Commit locally after the data guard, without pushing.

## 2026-11-15: R51t13 delivers simpler 6.3; prefix recovery was not achieved

6.2/6.3 default to no inhibitory usage updates; 6.3 removes state separation and retains per-connection transmission. All prefix conditions across 72 stages passed 0/2. Matched implementation is about 5.4% faster; proportional allocation about 46% slower without a capability gain. 929 members verified, pending=0; main work paused.

[Report](../../../lab/explorations/2026-11-15-kernel63/report.en.md)

## 2026-11-15: R51t16 authorizes inhibitory resource bypass, default on

The author requested a 6.3 inhibitory resource-bypass switch, enabled by default, and retention of optional independent resources only if the disabled option does not materially reduce performance. `inhibition_bypasses_resources=True` therefore bypasses inhibitory resource release, consumption, and the release-fraction multiplier. Excitatory resources, allocation, energy, thresholds, and learning retain their separate rules. Bypass takes precedence over independent resources: an independent inhibitory state is preserved but not used while bypass is on. Turning bypass off restores the selected shared/independent rule.

Earlier 6.3 snapshots lacking this field restore with false. Python, Rust, standalone runtime, and the configuration catalogue implement the change together. The global creation version remains 6.1. Other 6.3 defaults are unchanged; the historical successful prefix profile is not automatically made the default.

The performance comparison uses matched native builds with identical inputs and numerical states: option present but disabled versus a build without independent-pool support and with the same bypass rule. A repeated elapsed-time increase exceeding 20% requires removal. State size, event counts, and memory are also reported.

The registered scientific batch compares bypass on/off in three complete configurations, using two teaching blocks and the historical process criteria for both prefix discrimination and activity after a 300-second wait, totaling 72 stages. Actual defaults and the historical successful profile are reported separately. Both tasks must be tested under the same configuration before discussing coexistence. See the [R51t16 protocol](../../../lab/explorations/2026-11-15-kernel63/resource_bypass/protocol.en.md). This entry records authorization and design; measured conclusions follow separately.

## 2026-11-15: R51t16 implements inhibitory bypass and tests prefixes and sustained activity

6.3 now has an inhibitory resource-bypass switch, default on. Earlier snapshots lacking it restore with off; historical kernels are preserved. Keeping independent resources optional but disabled changed matched-state benchmark time by −0.3% to +2.5%, so the option remains, default off. All 72 stages, 144 states and 36 processes were verified. The complete prefix profile reproduced 2/2 in production 6.3 with scores identical to R51t15; an alternate profile disabling depletion and enabling facilitation sustained activity for 300 seconds at 2/2, but scored 0/2 on prefixes. Actual new defaults scored 0/2 on both, and no tested profile passed both. All 263 engineering checks passed; 946 archive members were read back, pending=0. In the dense 128-node benchmark, bypass increased per-connection execution time 13.50-fold; this dynamics cost is reported separately from retaining the option. Broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

[Report](../../../lab/explorations/2026-11-15-kernel63/resource_bypass/report.en.md)

## 2026-11-15: 6.3 restores three 6.1 defaults and retains local expiry

The author requested the 6.1 resource and usage-record behavior in 6.3, then explicitly retained local subthreshold expiry. Delivered defaults disable resource prechecking and inhibitory resource bypass, and enable inhibitory transmission-time updates; independent resources remain off and expiry remains on. Under the final expiry setting, prechecking reduced time by 8.40%, below the preregistered 20% threshold. Final 6.3 defaults changed time relative to 6.1 by −1.78% to +7.10% across four materials. The expiry-disabled compatibility configuration passed 72 boundary comparisons and all 24 paired benchmark final states. Actual defaults retain the behavioral difference in timely active-set settlement; the original zeroing floor and one-second quiet period remain. There were 654 distinct passing engineering tests; two database checks were skipped because the isolated test database was not running. Ten pre-edit 6.3 states and 19 historical implementation files remain unchanged. Python/Rust, standalone runtime and configuration catalogue are synchronized; the native module is installed, services were not restarted, and the application default remains 6.1. Historical scientific scores are preserved; broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

[Report](../../../lab/explorations/2026-11-15-kernel63/default_alignment/report.en.md)
