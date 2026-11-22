# R51h: learned bodily responses retain their correspondence across angle and gravity changes

13 November 2026. **Bodily associations in 6.1 transferred to the predefined new angle and gravity conditions: all 192 trained tests responded in the teaching direction, while all 48 untrained tests lacked a measurable directional response.** The joint-only condition passed 48/48 and the three conditions containing inertial input passed 144/144. The latter did not reproduce the historical reverse advantage. The registered process-transfer target was met, with no campaign stopping condition triggered.

## Purpose, expectation and method

Following R51f, this batch tested whether bodily sensation alone retrieves its previously paired marker response and whether that correspondence survives changes in physical parameters. It retained E18's four encoding-material blocks, ordinary and facilitation configurations, and five conditions: full sensation, joint-only, dose-matched full sensation, shuffled inertial samples and no teaching. The 40 parents came from R51f's complete one-second retention states. Originals were copied read-only and no further teaching occurred.

Each parent supplied six physical-cue copies: two poses under the original angle of ±0.7, a new angle of ±0.45, and gravity changed to −6, giving 240 conditions. Each cue contained 0.4 seconds of actual bodily measurements and no A/B teaching markers. One additional equal-duration blank copy per parent supplied the complete 5.6-second reference. These 40 controls filled the missing observation tail in the historical material. The number of independent material blocks remained four; condition copies did not increase independent N.

The frozen [protocol](protocol.en.md) recorded all four activity fields every 100 ms. Marker-channel peak increments and integrals were calculated by subtracting the blank trajectory from the cued trajectory of the same parent. A response counted in the teaching direction when the expected channel's peak increment exceeded 1e−5 and its integral exceeded the other marker by more than 1e−6. The converse counted as opposite; otherwise there was no measurable direction. The primary process window was 0.6–5.6 seconds after physical input began, with 0–0.6 seconds reported separately. The historical convergence measure was also retained.

The joint-only condition was expected to retain its original correspondence in all three scenes, with no directional response in untrained controls. For the three inertial-input conditions, reverse responses would reproduce the historical observation; original-direction responses would improve task performance. The original answers remained fixed.

## Results

The table combines ordinary and facilitation configurations. Each cell contains 16 tests: four materials, two configurations and two poses. Both configurations had identical cell-level counts.

| Sensory and teaching condition | Original scene: teaching direction | New angle: teaching direction | New gravity: teaching direction | Opposite | No measurable direction |
|---|---:|---:|---:|---:|---:|
| Full sensation | 16/16 | 16/16 | 16/16 | 0/48 | 0/48 |
| Joint-only | 16/16 | 16/16 | 16/16 | 0/48 | 0/48 |
| Dose-matched full sensation | 16/16 | 16/16 | 16/16 | 0/48 | 0/48 |
| Shuffled inertial samples | 16/16 | 16/16 | 16/16 | 0/48 | 0/48 |
| Untrained | 0/16 | 0/16 | 0/16 | 0/48 | 48/48 |

Both the input-phase and post-input process measures yielded 192/192 trained responses and 0/48 untrained responses in the expected direction. All 240 tests reached the historical convergence criterion, but both task markers were inactive at that endpoint. Converged marker expression therefore remained 0/240. The transient response and the converged state were scored separately.

## Analysis and scientific conclusion

**Experience-dependent bodily–marker correspondences in 6.1 can be retrieved by bodily sensation alone and transferred to the two new physical conditions tested here.** The trained–untrained difference identifies prior teaching as the source of directional responses. Copies of the same complete parent retained the correspondence in the original scene, at the new angle and under new gravity, completing the registered transfer test.

This is a favorable result for ThreeMind. Historical E18 recorded original-direction responses in 48/48 joint-only tests and opposite responses in 144/144 tests containing inertial input. With answers unchanged, both types now responded in the teaching direction. The reverse phenomenon is therefore not an inevitable feature of 6.1 on these materials. This comparison concerns whole versions and the declared measurement conditions; contributions of individual version changes belong to their corresponding mechanism studies.

The negative convergence result also has a definite interpretation: experience was expressed as a measurable response process, rather than sustained marker activation at the converged endpoint. These were separate preregistered targets. Process transfer passed; endpoint marker expression failed. Neither complete loss of joint-only responses in the original scene nor complete loss in the new scenes occurred, so the planned local-connection transfer study can proceed.

## Integrity, cost and delivery

Independent apparatus checks preserved complete endpoints through observation, save/restore and continuation. Read-only analysis verified 560 new initial/final states, 40 unchanged parents and 240 paired curves with two windows each. Independent 45-digit Decimal integrals differed from the scoring calculation by at most 6.94×10⁻¹⁸. Analysis did not load or advance Core.

Formal execution took 318.52 seconds, with peak private memory of 625.08 MiB. Pre-analysis files occupied 60.66 MiB logically and 65.42 MiB in allocated storage. The observed maximum network size was 12 nodes and 66 edges. All conditions completed without STOP or residual in-flight state.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/body-transfer61-v1/`. Research record: `7d6678b1-26ca-5888-83af-7a971f34faa0`. `analysis.json` contains condition-level and grouped results; `audit.json` records integrity and independent arithmetic checks. Final archival, complete API readback and pending status are recorded in `publication/completion.json`. Original parents, historical results and their reports remain intact.
