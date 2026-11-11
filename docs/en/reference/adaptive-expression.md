# Continually learned language-center adapter

[简体中文](../../zh/reference/adaptive-expression.md) · [Research boundaries](../plans/coadaptive-language-center.md)

`threemind.adaptive-expression/1` is an external adapter, not a new Core. It consumes original local processes accepted by graph-expression/2. Teaching labels update the peripheral only; inference never accepts them. Old readers remain available.

Python: create `AdaptiveExpression(capacity=64, device="cpu")`, call `teach(process, text, receipt=...)` for external demonstrations, `adapt(new_directory, steps=500)`, and `decode([process])`. Use `local_process(raw_trajectory)` to prepare observations. Restore with `AdaptiveExpression.restore(directory, device="cpu")`; subsequent updates always create another directory. Existing or partially failed output is not overwritten.

Weights continue, Adam restarts each update. FIFO teaching replay capacity2..128, default64; eviction affects only adapter replay, not original evidence. Checkpoints include weights, replay, parent and training metadata. No cross-window factual cache or fast-weight algorithm is claimed.

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_transformer.adaptive_expression_cli teach --input teaching.jsonl --output revision-1 --steps 500
& $py -m threemind_transformer.adaptive_expression_cli teach --parent revision-1 --input more-teaching.jsonl --output revision-2
& $py -m threemind_transformer.adaptive_expression_cli decode --parent revision-2 --input observations.jsonl --output utterances.jsonl
```

Teaching rows contain exactly `process,text,receipt`; inference rows contain only `process`. See [graph expression](graph-expression.md) for prepared observation format. Auto device chooses CUDA if available, otherwise CPU; explicit CPU is supported. Limits:128records,128MiB input,30min default wall time,RSS4/GPU3GiB and2GiB available RAM.

`return_utterance(reader, actual_text, encode, enabled=True)` optionally sends exactly the generated text through the existing encoder and input queue; disabled by default. Empty output is silence; incorrect words are not silently corrected. The caller supplies the instance's declared encoder. Teacher supervision, self-hearing and observer interpretation are distinct evidence. Successful adaptation alone cannot establish that semantic content originated in Core.

## Finite-vocabulary transcription diagnostic

`lab.tools.local_word_transcriber.LocalWordTranscriber` tests whether raw local processes distinguish actually heard words. It reads the same observations as a Transformer and does not replace the production expression adapter.

```python
from lab.tools.local_word_transcriber import LocalWordTranscriber

reader = LocalWordTranscriber(ridge=0.0001).fit([
    {"process": local_process(observation_a), "text": "甲。"},
    {"process": local_process(observation_b), "text": "乙。"},
])
utterance = reader.decode(local_process(new_observation))
reader.save("new-transcriber-checkpoint")
restored_reader = LocalWordTranscriber.restore("new-transcriber-checkpoint")
```

Channels and six raw fields at matching relative sample times become linear ridge features. There is an intercept, but no centering, counterfactual subtraction, per-example scaling or semantic node selection. Limits are node-only observations, 2–128 demonstrations and 2–32 words. It cannot generate unrestricted sentences. Previously unseen features receive zero trained weight and their count is returned. Scores are not probabilities. A fitted reader does not automatically adapt to later Core changes.

Teacher words are external supervision, never inference inputs. Learning to transcribe heard words does not guarantee translation of recalled or intended words; [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.en.md) tests these separately.
