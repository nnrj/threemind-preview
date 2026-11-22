# Performance of 6.3 versus 6.1 and the cause of the slowdown

2026-11-15. **On the ordinary workloads, 6.3 increased Rust advancement time by about 3% and Python time by about 6%. Repeated weak stimuli produced a substantial additional cost, primarily from timely activation settlement and the resulting node deletion and recreation.** This study measured performance and tested the cause without changing kernels, defaults, or historical individuals.

## Purpose, expectations and methods

The author requested a brief comparison and investigation of material slowdowns. Before running, we defined a 10% time increase as the scale requiring investigation. Advancement, input queuing, observation, complete-state serialization and restoration were measured separately. The design distinguished overhead from retaining optional mechanisms from the additional work performed after the weak-activation fix.

The main comparison used default 6.1, default 6.3, and 6.3 with only subthreshold expiry disabled. Actual birth defaults were used, including the original one-second quiet period. Rust had four workloads and the Python reference implementation two. Each condition had a warmup followed by six rounds in balanced order. Workloads meeting the registered retest rule received six additional rounds, with twelve as the limit. Within-round repetition counts were determined by preliminary timing calibration; these are engineering repetitions, not independent cognitive subjects.

The ordinary Rust workloads started with sparse connections among 128 nodes, dense connections among 128 nodes, or sparse connections among 512 nodes, followed by continuous inputs over 120 internal seconds. The weak workload sent four separate stimuli of strength 0.0001 every 0.1 seconds, cycling through 128 anonymous codes. Another channel received strength 0.3 every 0.5 seconds to sustain overall activity. Separate weak inputs formed no co-input connections: this was a local-maintenance stress test. Python used corresponding 32-channel workloads over 20 internal seconds. See the [protocol](protocol.en.md) and [input generator](bench.py).

## Performance results

Changes below are geometric means of paired time ratios across rounds, with the preregistered 95% bootstrap intervals. Negative values mean that 6.3 was faster.

| Advancement workload | Time change, 6.3 versus 6.1 | 95% interval | Rounds | Registered decision |
| --- | ---: | ---: | ---: | --- |
| Rust, sparse 128 nodes | +3.17% | +0.28% to +6.42% | 12 | Below the 10% investigation scale |
| Rust, dense 128 nodes | +3.18% | −2.28% to +6.99% | 6 | Below the 10% investigation scale |
| Rust, sparse 512 nodes | +2.97% | +2.41% to +3.54% | 6 | Below the 10% investigation scale |
| Rust, 128 weak-input channels | +33.49% | +15.67% to +51.26% | 12 | Pooled slowdown; separate-phase confirmation lacked precision |
| Python, sparse 32 nodes | +6.15% | +4.60% to +7.90% | 6 | Below the 10% investigation scale |
| Python, 32 weak-input channels | +78.77% | +76.03% to +81.37% | 12 | Both phases confirmed a slowdown above 10% |

The Rust weak-input decision preserves the original rule: both the initial and confirmation phases had to exclude zero increase separately. One unusually slow 6.1 round widened the confirmation interval to −1.28% through +35.74%, failing that requirement. All rounds remain included. The pooled twelve-round estimate and the independent diagnostic comparison below both show additional cost, but the separate-phase criterion is not scored as passed.

Absolute weak-workload times were short. Median Rust advancement over 120 internal seconds rose from 14.52 to 19.62 milliseconds; Python over 20 internal seconds rose from 47.33 to 84.67 milliseconds. These absolute times are medians, distinct from the paired geometric means above.

Input queuing and restoration stayed below the 10% slowdown scale on ordinary workloads. Observation and serialization were also broadly similar, but the sparse 128-node Rust workload remained noisy: changes were +4.21% and +5.29%, with upper interval bounds of +12.63% and +12.95%. These two outcomes retain the registered insufficient-precision label. All other ordinary observation and serialization upper bounds were below 10%. The [summary](summary.json) retains separate outcomes rather than a combined score.

Process peak commit did not meet the registered growth criterion of both 10% and 1 MiB; the largest median increase in advancement-stage peak commit was about 2.41%. Ordinary uncompressed JSON snapshots grew by at most about 0.65%. Weak-workload cleanup reduced the Rust snapshot from 87,642 to 12,023 bytes, a reduction of 86.28%, and the Python snapshot from 29,779 to 12,009 bytes, a reduction of 59.67%. Observation, serialization and restoration became faster in those workloads; peak process memory did not decrease proportionally.

## Cause: settlement adds work and enables existing cleanup rules

With subthreshold expiry disabled, 6.3 matched every numerical final-state field of 6.1 in 63 paired comparisons, including queues, nodes, connections and counters. Version identity and configuration metadata were excluded from that comparison. Weak-workload advancement also returned close to 6.1 timing, locating the principal extra cost in expiry handling.

To separate the causes, we ran the preregistered diagnostic after the main measurements: expiry on/off crossed with the existing node-retention option on/off. Each condition had one warmup and four measured rounds, using isolated engineering instances. The table reports median advancement times; all raw timings are retained.

| Expiry settlement | Retain nodes | Rust, 120 internal seconds / ms | Python, 20 internal seconds / ms | Rust expiry checks / deletions |
| --- | --- | ---: | ---: | ---: |
| Off | Off | 14.51 | 47.89 | 0 / 0 |
| On | Off, actual defaults | 19.51 | 84.79 | 9600 / 4800 |
| Off | On | 14.48 | 48.07 | 0 / 0 |
| On | On | 16.60 | 68.83 | 4800 / 0 |

With the fix enabled, weak positive activation is settled against the existing floor at the next internal microsecond. Nodes with zero activation, no effective connections and insufficient support then satisfy the existing local deletion rule. A later input with the same code creates a node again. The default Rust condition therefore performed 4800 activation settlements and 4800 deletion checks, deleting 4800 nodes; the final count fell from 129 to one. These are node deletions, not deaths of the whole individual: the additional regular input kept the individual active. The full-graph scan counter remained zero.

Retaining nodes removed deletion and recreation, reducing Rust time to 16.60 ms and Python time to 68.83 ms. Remaining costs include activation settlement, active-set updates and local timer maintenance. Python profiling likewise found 1600 additional expiry checks and 800 node deletions under defaults; retention left 800 expiry checks and no deletions. Profiles were collected separately and excluded from normal timing. They do not establish Rust function-level time shares.

**The cause comparison establishes that the weak-workload slowdown comes from additional maintenance after the fix and repeated recreation once existing deletion rules execute. Retaining optional configurations did not produce a general slowdown of this magnitude.** One of the four Rust diagnostic rounds with expiry off and deletion permitted took 33.29 ms. It remains in the raw data; the table uses the registered four-round median, without excluding samples. The diagnostic explains the cost and does not replace the failed separate-phase statistical requirement above.

## Conclusion and recommendation

The study completed its objective of measuring performance and identifying the cause of a material slowdown. Default 6.3 has small overhead on the ordinary workloads tested, while local maintenance of repeated weak inputs is substantially more expensive. The fix also removes stale nodes and reduces final snapshot size, so the added work is not entirely waste.

We recommend retaining the fix. If later tasks contain substantial weak-input traffic, optimization should target local settlement, timer registration, and node deletion/recreation while preserving complete states and event order. Making node retention the default, changing the zeroing floor or disabling the fix would alter behavior; none was implemented. This study did not measure large shape–color, ecological or prefix-task performance. Broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

## Evidence, reproduction and instrumentation corrections

The comparison and diagnosis used 235 worker processes, with 235 complete final states verified. Timing and warmup involved 2868 newly created engineering instances, plus four separate Python profiling instances. Measurement through diagnostic completion took 670.22 seconds; raw evidence occupies 12,840,030 bytes, within the 20-minute and 256 MiB budgets. Minimum sampled free commit, physical RAM, C-drive space and E-drive space in the main comparison were 13.54, 12.26, 9.33 and 58.85 GiB. All workers have ended and no incomplete marker remains.

Complete evidence is in the ignored `.work/kernel63-performance-20261115/` directory. The [summary](summary.json), [diagnostic summary](diagnostic-summary.json) and [final audit](audit.json) contain counts, intervals and hashes. Observation and saving preserved the complete state, and restoration reproduced its hash; frozen source and protocol files were unchanged. These engineering workloads were not registered as new cognitive experiments, and no research-API completion is claimed.

Final read-only verification corrected two instrumentation records. First, state IDs use canonical hashes; the diagnostic runner's final audit incorrectly compared them with raw JSON-byte hashes. That assertion occurred after all measurements and 40 states were complete. The new [verifier](verify_diagnostic.py) used the correct algorithm and passed all 40 states without rerunning measurements or altering evidence. Second, the preregistered native-module path resolved to the Python package loader rather than the `.pyd` extension. The preceding default-alignment summary's `native_sha256` also identifies that loader. The actual binary hash and its modification time preceding the run are now recorded separately in [audit.json](audit.json), explicitly as a post-run record rather than a preregistered hash. Earlier reports and manifests are preserved.
