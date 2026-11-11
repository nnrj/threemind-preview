# E69 interim gaze teaching and test replay, version 1

On October 14, 2026, the user requested an interim video to see the progress of gaze learning, provided this would not disturb the experiment. The new `preview_gaze.py` reads committed originals and reuses the frozen renderer's sampling parser and retina drawing. It does not import the experimental subject, restore it, advance Core, or modify frozen curriculum, records or source.

Video: `E:\ThreeMindData\experiments\2026-10-13-eye-hand-shape-color\continuations\r1\previews\gaze-progress-v1\E69_注视学习阶段回放_第1版.mp4`. Duration **6:25**, 1440×1080, 12fps, H.264, 2× speed, 13,126,099 bytes. SHA256: `101444aeff22b15cb5be39ddd41b57f6cccda532a81fb76a9b5788f6d80076d8`.

| Video start | Content |
|---|---|
| 00:07 | Initial assisted demonstrations in four directions |
| 00:28.5 | All 24 initial autonomous tests, 0/24 |
| 02:09 | First corrective-teaching excerpts |
| 02:32 | All 24 tests after correction 1, 15/24 |
| 04:13.5 | Second corrective-teaching excerpts |
| 04:36.5 | All 24 tests after correction 2, 16/24 |

The video includes 12 assisted lessons and every question of three development tests. Successes and failures have identical playback/hold treatment. The left top view shows the camera's clear region projected onto the actual marker height of 0.52m, the visible purple marker and actual green hand position/trajectory. The right panels show recorded retinal input and magnified central sampling. Assistance, own intent, eye angles and velocity are labeled separately. Omitted intervals are explicit forward jumps in video time, not experiment resets. The authorized second-2004 restoration is disclosed in the video; original interrupted evidence remains intact.

Four bottom plots show measured node totals for activation, inhibition, direct and associative contact over the preceding 30 simulated seconds. Each has a labeled independent linear scale. Gaps are not interpolated. Video speed and result holds do not affect simulation time. Scores describe autonomous development tests, excluding assisted lessons; they are not coordination, semantic or final-test results.

Validation: all 236 source-file hashes agree before/after rendering; full video decoding passed. Teaching, failed and successful frames were inspected, including an encoded-video frame at 303.5s. Text, retinal panels and all four curves are legible. Latest/in-flight/STOP/continuation control hashes are unchanged after rendering and publication: boundary741 / second4062 remains a complete resource pause, with no added rollback, birth or simulation step. `visual-review.json` supplements the unchanged automatic `export.json`.

The video and 14 supporting files were registered by reference to the same E69 record `cddd5824-bcf9-5371-a8ae-f80e2f79ef03`. Video evidence ID: `cce271f6-09f0-5a41-a2bc-1eae4e49a2b3`. Reading the whole video through the formal API reproduced its byte count and SHA256; pending=0. E69 was not finalized. Receipts remain in the preview directory; original data are outside Git.

Measured autonomous gaze improved from0/24 to15/24 and16/24. Of the latest16 successes,15 entered the clear region from outside and one maintained an initially centered target. Correction round3 is unfinished; coordination and semantics have not started. See [HANDOFF](HANDOFF.md) for live-state procedures and host policy; the formal experiment still needs continuation.
