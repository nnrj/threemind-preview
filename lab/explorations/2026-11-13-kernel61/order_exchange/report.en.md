# Connection weights carry event order: state-exchange replication in 6.1

14 November 2026, R51o. **Exchanging connection weights formed by opposite teaching histories exchanged response direction in the registered order task after a 30-second delay.** All 16 weight-only conditions followed the donor. The complete factorial experiment also reproduced historical E21: all 128 conditions including weight exchange followed the donor, while all 128 excluding it retained the recipient direction.

[中文](report.zh.md) · [Preregistered protocol](protocol.en.md) · [Preceding retention study](../order_recall/report.en.md)

## Purpose and method

R51n established that the same X cue produces different A/B responses after AX-before-BX and BX-before-AX teaching. At 30 seconds, activation of A, B and X had subsided. This study asked which internal states carry that order difference. The expectation was that exchanging weights alone would transfer direction, while exchanging other states would preserve it.

The design retained four anonymous material blocks, facilitation time constants of 0 and 1 second, and two teaching orders, giving 16 references. Research copies continued from complete R51n teaching endpoints at 6.8 seconds, waited 30 seconds under the original schedule, and reached the exchange boundary at 36.8 seconds. Donor and recipient shared configuration, anonymous channels, topology and time but had opposite teaching histories. Original teaching subjects and records remained intact.

Four groups were exchanged: W, base connection weights; S, connection decay age and usage history; N, persistent node state and usage history; and D, rapid node activity, short-term enhancement and synaptic resources. All 16 on/off combinations received an X=0.5 cue and a matched no-cue probe, giving 512 single-test diagnostic copies. The protocol lists exact fields. Each five-second response recorded all nodes' activation, inhibition, direct and associative activity every 20 ms. Matched no-cue integrals were subtracted from the A and B activation integrals before calculating their difference; the threshold was 1e−6 activation·seconds.

The four blocks mainly vary anonymous encoding. Configurations and diagnostic copies are nested within these materials; the counts of 16, 128 and 512 below refer to conditions or copies, not additional independent samples.

## Results and scientific conclusion

| Registered target | Expected result | Observed result | Decision |
|---|---|---|---|
| Weights alone transfer direction | All 16 references follow the donor above threshold | 16/16; all four blocks pass | Pass |
| Every combination including weights transfers direction | All 128 follow the donor | 128/128 | Pass |
| Every combination excluding weights retains direction | All 128 follow the recipient | 128/128 | Pass |

The table gives the recipient's originally later-taught target minus its earlier-taught target, using net activation integrals in activation·seconds. Positive values retain original recency; negative values follow the oppositely taught donor. Values are identical across four blocks and both teaching directions within each facilitation configuration.

| Exchange | Facilitation off | Facilitation 1 s |
|---|---:|---:|
| Empty exchange | +0.001730154776 | +0.002027352955 |
| Connection history S only | +0.001730164436 | +0.002027365284 |
| Node history N only | +0.001730154776 | +0.002027352955 |
| Rapid states D only | +0.001730154774 | +0.002027352952 |
| Weights W only | −0.001730164433 | −0.002027365281 |
| All four groups | −0.001730154776 | −0.002027352955 |

**Weights causally carry the order information expressed in this task.** In weight-only conditions, node activity, connection age and other history variables still belonged to the recipient, yet response direction followed the donor. The factorial controls also reject the explanation that transferring the full rapid-activity state is necessary to transfer direction.

For example, in block 100121 with facilitation off and AX taught before BX, X→A and X→B weights were 0.0901706193 and 0.1352019850. Opposite teaching exchanged these values. Each weight-only intervention changed four directed connections, or 64 across the 16 references. Topology and channel addresses were unchanged, and the readout remained fixed.

The other exchanges made real changes too. Connection-history exchange changed decay age and usage counts, node-history exchange changed support and related fields, and rapid-state exchange changed tiny residual inhibition, traces and short-term enhancement. Their effects on response magnitude at this time were small, and none of their combinations reversed direction without weights. Serialized historical fields inactive under the current configuration were retained without inferring function from their names. This result identifies the carrier of expression after 30 seconds; formation during teaching remains a separate question in the approved plan.

Historical E21 likewise passed 16/16 weight-only transfers, 128/128 transfers including weights and 128/128 retention conditions excluding weights. The new 6.1 states reproduce that causal pattern. Together with R51n, the result establishes that **task nodes need not remain active to preserve this order experience: experience-formed connection weights retain order differences and organize responses when a new cue arrives.** This supports ThreeMind's mechanism of experience-dependent activity.

## Intervention checks and resources

On declared research copies, the existing configuration API settled lazily stored quantities to the current time without changing configuration or advancing time. All before/after changes were retained. The independent apparatus passed 64 native save/restore checks and 64 exact self-exchanges. Formal empty exchanges differed from the original R51n response trajectories by at most 1.734723475976807×10⁻¹⁸, below the preregistered 1e−12 tolerance.

When weights or decay age changed, the tool updated local deletion deadlines using existing equations and recorded those derived changes. The earliest affected deletion deadline was 58,470,329,200,000 microseconds, far beyond the probe endpoint of 41,800,000 microseconds, so deletion scheduling cannot explain direction changes within the response window. Production Core, defaults, curricula and original individuals were unchanged.

Read-only checks verified 1,856 states, 6,336 inputs, 528 stages and 256 exchanges. Of these inputs, 960 belong to the 16 waiting copies and 5,376 cue/maintenance frames match historical E21. Independent 45-digit decimal arithmetic found a maximum integral discrepancy of 6.938893903907228×10⁻¹⁸. Analysis created and advanced no kernels.

Scientific execution took 408.58 seconds, or 6.81 minutes, with peak private memory of 575.32 MiB. Pre-analysis originals occupied 69.41 MiB logically and 83.58 MiB of allocated storage. Comparable per-unit file measurements were 1.432–1.440 times historical values, below the frozen 1.5-times estimate. No resource pause or incomplete state occurred. Both scientific targets passed; the planned timing study follows.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/order-exchange61-v1`. Research record: `34ce81e3-3afa-5ec2-88b6-734143071273`. The archive, manifest and full API readback receipt are `originals.zip`, `manifest.json` and `publication/completion.json`; closure requires verified coverage and pending=0. This is a within-project replication. Artifact recomputation and AI review are identified separately from independent reproduction by external researchers.
