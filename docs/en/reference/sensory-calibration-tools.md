# Sensory calibration and reciprocal-association instruments

[中文](../../zh/reference/sensory-calibration-tools.md) · [E45 registration](../../../lab/explorations/2026-10-05-language-calibration/design.en.md)

2026-10-05. External research only; Core and existing sensory protocols are unchanged.

`lab.tools.sensory_calibration` exposes explicit dose/repetition/simultaneous/reverse interventions, declared shared visual acquisition, actual-time trajectory integration and frozen physical-response-library comparison. Same-time separate frames are not a merged frame; intensity remains independent so dose controls do not accidentally invoke extra strong-stimulus learning. Brief responses are retained without a stability gate. Zero or ambiguous activity has no forced winner. Preserve complete original trajectories.

Humans and agents can use the same Python API or offline JSONL CLI:

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.sensory_calibration --library library.json --input processes.jsonl --output observations.jsonl
```

The observer receives anonymous channel activity and fixed templates, not queries, answers or formal teaching assignments. It compares physical-response patterns, not subjective images; five measured rays cannot reconstruct an entire scene. Older readout criteria remain available.

Numerical convention: `process_vector` divides its trapezoidal integral by window duration, yielding a time-weighted mean. A higher sample count alone does not imply stronger activity. For equal-duration windows the integral differs only by a constant. E45 preserves both the two-second primary measure and its fixed short windows; a better-performing short window cannot retroactively replace the primary measure.

`lab.tools.oscillator_sensor.OscillatorSensor` records mass, spring stiffness, damping, waveform, sample rate and fixed filterbank energies. This explicit simulated oscillator is neither a full sound field nor a biological cochlea. Object identities/note names never enter Core.

E45's `experiment.py` provides prepare/sensory/select-input/parameters/select-parameters/formal/summary; `visual_reader.py`, `expression.py`, `composition.py`, `interventions.py` and `continuous.py` provide the registered observation/training/control stages. These scripts are a frozen study with independent storage, budget and project, not an overwrite command for arbitrary existing studies. New research expression heads are not the default live chat device.
