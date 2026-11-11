# E55 complete experiment film

2026-10-06.[简体中文](video.zh.md) · [Report](report.en.md).

The user clarified that the complete experiment should include multiple groups and both correct and incorrect outcomes. The film therefore includes every completed E55 group with recorded temporal evidence, rather than only the best recent-window group or successful movements. Different studies are not presented as one continuous consciousness history.

Files live under`.work/grounded-reviews-20261006/complete-media/`:

- `e55-complete.mp4`:28min42.4s,1600×900,20fps,no audio,embedded chapters.
- `complete-replay.html`:the same interactive canvas, chapter selection, playback, seeking and screenshots; no Core, Docker or online model required.
- `complete-replay.json`:48,104 recorded display samples. Full stimuli/node states remain in the original archive. RGB is converted to8-bit display colour only.
- `media-plan.json`,`video-manifest.json`,`display-check.json`:source mapping, chapter timing, encoded media and display acceptance. Database artifact IDs are in repository`media-delivery.json`.

Coverage: each classroom's168 lessons and96 calibration observations;280 formal questions, including48 silenced-edge and8 rescue trials;180 motor demonstrations; all32 autonomous movements for each of three heads. Teaching/calibration plays at4x, intervals at8x, formal tests at1x with extra result holds. No lesson, group or unsuccessful test is omitted. Accelerated video need not display every source sample as a separate frame; interactive data retains every recorded sample, with sample hold and no invented trajectories.

Question trials preserve their real teacher-pointer sensory input. Motor tests have neither teacher marker nor teacher-applied force; orange goals are observer-only scoring. Each question/action restores its source snapshot independently. Complete sentences are displayed for readability while original delivery remains character by character. Recorded answers appear after their observation windows, without new inference.

Offline fitting/statistics have no physical trajectories and receive no invented training animation. Unexecuted controls produce no false replay. An initial partial encode was stopped to clarify the wording distinguishing genuine question-pointer input from scoring-only motor targets; the partial file is retained and the display re-encoded without simulation.

Chapter times and source files are in`media-plan.json` and the [Chinese table](video.zh.md):normal teaching00:12,calibration02:42,strict QA03:35,untaught combinations05:27,new arrangements06:07,edge silence07:59,rescue09:51;no-learning teaching10:13,calibration12:43,QA13:37,untaught15:29,new arrangements16:09;all motor demonstrations18:01;recent-window tests21:32,full-process tests23:50,validation-selected exploratory tests26:08.

## Descriptive approach check

In response to the user's observation, existing recent-window trajectories were reread without simulation. By0.25s,23/32 move closer to the requested object, but30/32 also move closer to the scene centre. The requested object has the largest distance reduction among the four in only4/32 trials. By2s,17/32 are closer than at action start and1/32 reaches. Values are recorded in`approach-description.json`.

Early approach is real, but target-directed selection and general centreward movement must be separated. This is not a random-action control and cannot itself exclude target-related internal activity. Future same-scene/request-switch and fixed/random-action comparisons remain recommendations, alongside separating selection from execution; none is newly run here.

Use`media.py prepare`only once; existing complete replay is preserved. `tools/export_classroom_replay.mjs --input complete-replay.html --output new-output.mp4 --ffmpeg executable`exports the same UI canvas;`--preview-only`checks display. Limits:two encoding threads,20-minute wall budget,512MiB per video; existing movies are not replaced. This is media delivery, not new training or a Core/default change.

## Encoded-media acceptance

Verified H.264,1600×900,20fps,34,448 frames,18 chapters and1722.4s; file size54,146,057 bytes. An action frame and the ending were decoded from the actual movie and visually checked. Wide/narrow playback,chapter selection,seeking and screenshots pass. Movie and interactive viewer are appended in a new record in the same project. Combined study-local files,archive and database growth are about4.01GiB,within budget; old evidence is not rescanned.


## 2026-10-06 addendum: actuation behind two circles

The user reports2:27–2:35and12:28–12:38. After E56's main study, map them to original E55 frames: normal/nonlearning teaching intervals, no Core motor command or teacher marker. At identical simulated times, pointer locations match exactly (maximum difference0metres), although normal associative peaks exist and the nonlearning signal is zero. Wind and body mechanics produce these circles; they do not establish attention seeking. This neither denies recorded internal activity nor judges other autonomously controlled intervals. Actuation provenance was insufficiently prominent in the old movie. Append clarification without replacing the movie or experiment.[E56 audit](../2026-10-06-vision-correction/report.en.md)


### 2026-10-06 follow-up: learning off is not Core off

The user correctly noted that a deterministic consciousness can repeat a trajectory under repeated input, so identical learning-on/off paths alone do not exclude its contribution. After the main study and video, an independent **physical-world-only control creates no Core**, retaining the initial body, weather, objects and teacher scene schedule. It advances 516 simulated seconds without feeding recorded positions or activity into control. All 10,320 positions and ten physical measurements match, including both circles; computation takes 5.20 seconds and the trace is 1.17 MiB. Combined with the original interval's disconnected Core motor output, this establishes physical actuation for these particular circles. Regularity itself is not evidence against consciousness, and concurrent associative activity remains recorded. Keep the first audit and add this stronger control. Activity-driven circling and visible self-limb experiments remain separate follow-ups.

[独立重算 / Independent rerun](../2026-10-06-vision-correction/circle-core-disabled.json) · [新报告 / New report](../2026-10-06-vision-correction/report.en.md)
