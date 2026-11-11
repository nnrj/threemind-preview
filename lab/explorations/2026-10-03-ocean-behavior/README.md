# E31 · Ocean behavior attribution

[设计 / Design](design.zh.md) · [English design](design.en.md) · [原位补试 / Shared-world probes](natural-registration.md) · [执行更正 / Corrections](execution-notes.md)

This study uses copied E30 states and the unchanged `continuous-memory/2` and Ocean/3 implementations. It does not turn off ordinary learning, forgetting, inhibition or finite energy. Evidence is separate under `.work/ocean-behavior-20261003`; original data remain read-only. Re-running a completed case skips it. A partial directory requires a separately named continuation, never overwriting its evidence.

Use the project Python environment, from the repository root:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py lab/explorations/2026-10-03-ocean-behavior/experiment.py trials --donor g0-i10 --phase all
& $py lab/explorations/2026-10-03-ocean-behavior/natural.py --group 0
& $py lab/explorations/2026-10-03-ocean-behavior/analyze.py
& $py lab/explorations/2026-10-03-ocean-behavior/process_analysis.py
& $py lab/explorations/2026-10-03-ocean-behavior/natural_analysis.py
```

The registered study has resource guards and requires a fresh actual account-usage receipt. Do not invent usage values. Registration is one-time; the commands above refer to this study's already registered donor copies, not arbitrary user instances.

Reusable external tools:

- `lab.tools.ocean_behavior`: isolated physical scenes, matched structural copies, exact recorded action controls, observation and activity-based region selection.
- `lab.tools.ocean_encounter`: prospective encounters and whole-world copy observation. No activity or target label is written into Core.
- `lab.tools.ocean_video`: actual-recording PNG/MP4 export and a validated JSON plan; no model execution or frame interpolation.
- `threemind-ui/src/v2/visualCapture.ts`: typed browser PNG/WebM capture API, also used by the visible controls in network and physical-world views.

## Screenshot and video export

```powershell
& $py -m lab.tools.ocean_video --template
& $py -m lab.tools.ocean_video <case-directory> <new-output.png> --at 2.5 --plan <export-plan.json>
& $py -m lab.tools.ocean_video <case-directory> <new-output.mp4> --plan <export-plan.json>
```

An export plan can set `title`, `start_s`, `end_s`, `fps`, `speed`, `focus`, `view_m` (null for the whole world), `show_title`, `show_legend`, `show_world`, `show_generation`, `show_time`, and `show_trail`. MP4 requires FFmpeg on PATH; the Python API additionally accepts an explicit `ffmpeg` executable path. PNG does not require it. Export only actual recorded intervals, up to 300 video seconds, 1920×1080 and 30 fps. Existing files are refused. A JSON receipt identifies the recording, selected interval and non-interpolated sampling. MP4 frames can repeat when export fps exceeds evidence sampling frequency; they do not create extra observations.

UI: use **截图 / 录屏** beneath the consciousness graph or physical-world preview. Advanced options show titles, legends, available world/generation/time metadata, recording fps and time limit. Browser capture saves PNG/WebM, up to 300 wall-clock seconds and approximately 128 MiB; leaving the view stops capture. Only the displayed observation canvas is recorded, without desktop or microphone access. Changing recording fps does not change simulation time. An unavailable metadata field is omitted, not inferred.

Browser capture and offline export have different clocks: the former records the current visible view in wall time; the latter replays recorded simulation time at an explicit speed. Their labels have the same meaning, but the plans are distinct typed interfaces. Leaving or switching the view ends and downloads the recorded clip. For comparative research clips, prefer offline exports with receipts and retain the source data.

If a running consciousness receives live host telemetry, recording load can indirectly become part of that input. This study does not use that feedback. Offline exports use only saved observations and introduce no such feedback.

## Checks

Focused tests: `tests_v2/test_ocean_behavior.py`, `tests_v2/test_ocean_encounter.py`. `check_capture.mjs` uses a private Vite fixture with no backend at port 25071; it tests actual screenshot and WebM downloads at 1440/390 pixels. The fixture uses synthetic moving geometry solely to test capture, never as experimental evidence. Study videos are rendered from actual experiment trajectories.
