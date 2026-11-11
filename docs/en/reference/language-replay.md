# Teaching replay, screenshots and video

2026-10-05. [简体中文](../../zh/reference/language-replay.md)

Open **Dialogue experiments → Teaching replay & video**, then select a project with a saved replay. This film is stored in the E52 coadaptive-language project. Play, pause, seek chapters, adjust viewing speed, capture PNG, record WebM, or open a local replay JSON. Desktop shows scene, activity and dialogue together; narrow screens offer separate views and a selectable text transcript.

Recording starts playback at the current position and saves the complete landscape view. Seeking changes the recorded content. Existing capture options control title, source, time, legend, frame rate and duration: at most 300 seconds, 30fps and 128MiB. Extra footers default off because the scene already includes these labels. Empty browser recordings produce an error rather than a zero-byte download; very short recordings may need a longer duration. A published MP4 can be downloaded directly.

## The delivered film

**When experience becomes an answer: 17 chapters, 3 min 44 s, 1080p at 15fps, Chinese captions, no audio.**

- E50: recorded repeated teaching and spaced review for source223; four new-view naming examples and reversed teaching. The 74/80 figure is the original early naming result across two sources, not an independent statistic from the four selected examples.
- E50: normal, targeted silencing, matched silencing and rescue in independent copies of one snapshot with a frozen decoder. They are not four sequential manipulations of one continuously running instance.
- E52: a separate course/decoder with real “What is it called?” dialogue, one wrong red-ball answer, one correct blue-ball answer, and subsequent teacher demonstrations. These batches are not one continuous learning history and do not establish open-ended conversation.

Some E50 probes provide vision only; the film does not invent a spoken/text question. E52 answers precede that round's correction. Activity after correction was not saved and is not fabricated. Answers are taken from existing records without new inference.

Objects are illustrative reconstructions from original definitions. Original vision consisted of five ray distances and RGB values; scene labels are for viewers. Anonymous node positions are a display layout, not brain regions. Edges use a fixed display sample without invented propagation particles. Simulated time and the last recorded sample time are shown, and samples are held without interpolation. Quiet activity is not artificially illuminated. Teaching had no saved edges, so only nodes are drawn there.

[Sources and chapter manifest](../../../lab/demonstrations/2026-10-05-language-replay/manifest.json) · [E50 report](../../../lab/explorations/2026-10-05-graph-expression/report.en.md) · [E52 report](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md)

## Reusable tools

`threemind.language-replay/1` contains chapters, original events, samples, anonymous channels, illustrative objects and source references. Files are limited to32MiB,15minutes,100chapters and10000samples. This is a derived visual artifact, not a replacement for complete evidence. Large original evidence is not loaded wholesale. Project artifacts carrying this schema appear in the replay page; the listing uses the platform's latest200 artifacts, while older files remain usable through local import. The player only uses GET requests, with no stimuli or run commands.

React and offline MP4 share `LanguageReplayRenderer`. Each export frame is evaluated at an explicit replay time; rendering speed does not change experimental time. No Core is instantiated or advanced. The command uses project Node dependencies, installed Edge and FFmpeg, starts its own Vite preview and closes it afterward without taking over a user service.

```powershell
node tools/export_language_replay.mjs --input .work/language-replay-20261005/language-replay.json --output .work/language-replay-20261005/reexport.mp4 --fps 15 --ffmpeg D:/DevTools/ffmpeg/bin/ffmpeg.exe
```

`--preview-only` generates inspection images. Existing MP4 files are not overwritten. Export is bounded to20wall-clock minutes,512MiB and2FFmpeg encoder threads; it does not retain thousands of PNGs. This film took approximately139seconds to encode and occupies approximately5.4MiB. CUDA, Docker, online models and paid providers are unnecessary. JSON, video and poster are appended through existing Lab artifact services to E52, together with a separate demonstration record; original reports are unchanged.

## ThreeJSON assessment

This React/Canvas2D film mainly presents text, controls, charts and a few objects. Inspection of local ThreeJSON commit`7acc656` documentation and entry points confirmed dynamic point/segment batches, timeline`renderAt/seek`, and image/video export via`@threejson/media-kit`. These suit future3D teaching, robotics/ocean scenes and larger networks. Introducing it solely for this film is not necessary; no dependency was added and no comparative performance benchmark was claimed. Future integration should render explicitly timed saved evidence, avoid replacing activity with particle simulations, and verify the available package version rather than assume npm matches repository capabilities.

This is a visualization delivery. Production coadaptive dialogue UI, reliable translation of new experiences, and emitted-output-bus research remain separate open tasks.
