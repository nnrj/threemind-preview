# Multimodal Sensory and Output Adapters

[中文](../zh/multimodal-sensory-and-output-adapters.md) | [English](multimodal-sensory-and-output-adapters.md)

## Boundary and purpose

ThreeMind implements four pluggable devices: auditory sensation, visual sensation, acoustic output, and activation-image projection. They remain outside Core:

```text
audio / image / video / microphone / camera
  -> non-semantic decoding and sensory sampling
  -> anonymous SensoryFrame sequence
  -> InputBus
  -> ThreeMind Core
  -> anonymous OutputFrame
  -> acoustic output organ / activation-image projector
```

Core does not know what WAV, pixels, cameras, frequency bands, characters, or objects mean. The adapters use no speech recognition, OCR, object classifier, pretrained embedding, or language model. Each consciousness maps the same physical features through its own `sensory_seed`, so an adapter defines access and resolution rather than meaning.

The four devices are available in the host registry by default, but their bindings are off in a newly created model package. Uploading a carrier or deliberately enabling microphone, camera, mouth, or image output explicitly enables both the host device and current package binding; the resolved configuration is then written into the package.

## Auditory sensor

Uploaded audio is decoded by the host to mono physical samples. A live microphone sends `float32` PCM. `auditory-sensor` resamples and frames real samples, then applies one selectable physical encoding:

- `band-energy`, the default, is a small deterministic bank of frequency-energy measurements, not speech recognition;
- `waveform` divides a time window into bins and preserves a less transformed physical contour through separate positive and negative anonymous channels; zero amplitude is never shifted into a continuous drive.

Each feature may expose anonymous `level`, `rise`, and `fall` channels. Falling activity has its own non-negative channel because Core does not treat a negative value as a different excitation. Zero drive is omitted, while a transition from a positive value to zero remains observable through `fall`. The first frame only establishes the change baseline. Short AudioWorklet blocks are retained until a complete sensory window exists; zero padding does not invent silence at every browser packet.

Configuration covers target sample rate, sensory frames per second, band count and range, waveform bins, level/change switches, gain, input epochs between frames, and upload limit. Live microphone access is off until explicitly enabled.

## Visual sensor

The host decodes uploaded image/video carriers to pixels. A live camera produces low-resolution grayscale frames in the browser. `visual-sensor` offers deterministic physical filters:

- `luminance`, the default grayscale level;
- `edges`, local Sobel edge magnitude;
- `threshold`, an explicitly configured binary sample.

None recognizes an object or generates semantic ASCII art. After resizing to the configured retinal dimensions, the adapter emits local patches in order. This preserves local adjacency and temporal structure and avoids placing every pixel in one co-activation event, which would accidentally instruct the graph to create quadratic whole-image connectivity. Pixels can expose `level/rise/fall` channels.

Configuration covers retinal size, maximum frame rate, patch size, filter and threshold, level/change switches, gain, input epochs between patches, and upload limit. Live camera access is off until explicitly enabled.

## Output organs

`acoustic-output-organ`, labelled “Mouth” in the UI, subscribes directly to anonymous OutputBus frames. It deterministically maps node identities and activation to a bounded set of oscillator frequencies and amplitudes. It never reads observation labels and performs no text-to-speech. Early output may therefore be noise or a tone pattern. Any later repeatable stimulus–activity–sound relation requires controlled external decoding; the organ does not write that meaning in advance.

`activation-image-projector` maps anonymous node identity and activity into a fixed-size grayscale image. It is not claimed to be a biological organ; it is an external experimental output device and also ignores labels.

Output uses bounded latest-frame buffers and configurable send intervals. A slow browser may miss old presentation frames, but it cannot block Core or edit the network.

## UI, protocol, and audit

Above the text composer in the right-hand Stimulus panel are `+`, Ear, Eye, Mouth, and Image readout controls:

- `+` uploads audio, an image, or video;
- Ear and Eye start/stop browser microphone and camera access;
- Mouth and Image subscribe to anonymous acoustic controls or grayscale projections;
- permission, upload/encoding progress, errors, and active state receive immediate feedback.

The live binary protocol is `threemind-media/1`. Every packet declares sequence, capture time, and physical format. The server rejects out-of-order, malformed, oversized, or type-mismatched packets and applies the configured visual frame-rate ceiling again. Pause, disconnect, and stop reset change baselines instead of turning an interruption into a false spike.

Uploaded carriers use SHA-256 content-addressed retention under `data/media/`; identical content is stored once. Streaming writes enforce the limit without loading the complete carrier into memory. Raw microphone and camera content is ephemeral. Only the session, anonymous-frame count, InputBus `envelope_id`, and delivery audit are retained. `data/media-audit.sqlite3` can be queried and exported as CSV or JSONL:

- `GET /api/media/capabilities`
- `POST /api/media/uploads`
- `GET /api/media/sessions`
- `GET /api/media/deliveries`
- `GET /api/media/export?format=csv|jsonl`
- `WS /api/media/input/{consciousness_id}/{adapter_id}`
- `WS /api/media/output/{consciousness_id}/{adapter_id}`

## Dependencies and graceful degradation

The standard library always supports PCM WAV. Browser PCM and grayscale live streams need no media codec package. Compressed audio, video, and common uploaded images use the optional media extra:

```powershell
python -m pip install -e ".[media]"
```

Missing dependencies never prevent service startup. Adapter Management reports partial availability and the specific missing capability; it never substitutes a fabricated zero measurement.

## Experimental interpretation boundary

There is no forced brain-region rule. Auditory banks and the visual retina use separate anonymous channel namespaces. Any functional region should arise from repeated sensory coupling, local connectivity, forgetting, consolidation, spatial conditions, and inhibition. `receptor_topology` is audit metadata that Core never reads. A future forced-region control must be default-off, explicitly recorded, and reported separately from naturally organizing conditions.

The same carrier maps to different anonymous channels under different seeds, and different sensor settings expose different information. Comparative work must preserve the package, sensory configuration, carrier checksum, delivery order, background condition, and output settings. Speech-like sound, object-like images, or differentiated regions are candidate observations, not standalone evidence of understanding or subjective experience.
