"""Same-data, word-only linear instrument diagnosis; no task-answer teaching."""
from experiment import *
from lab.tools.local_word_transcriber import LocalWordTranscriber


def main():
    torch.set_num_threads(2)
    s = study()
    a = adapter()
    try:
        s.allow_extension()
        for seed in (223, 279):
            path, tick = start(s, f'linear-transcription-s{seed}')
            if tick is None:
                continue
            if (s.completed_count or 0) + s.extra_core_copies + 4 > s.settings.instance_limit:
                raise RuntimeError('four literal-word probes exceed budget')
            shutil.copy2(ROOT/'lab/tools/local_word_transcriber.py', path/'local_word_transcriber.py')
            calibration = WORK/'cases'/f'transcription-s{seed}-stage0'/'expression'
            with gzip.open(calibration/'teaching.jsonl.gz', 'rt', encoding='utf-8') as stream:
                samples = [json.loads(line) for line in stream]
            head = LocalWordTranscriber().fit(samples)
            head.save(path/'reader')
            fitted = [head.decode(r['process'])['text'] for r in samples]
            original = AdaptiveExpression.restore(calibration, device='cpu')
            source = WORK/'cases'/f's{seed}-feedback-stage0'
            heard = []
            for item, word in enumerate(NAMES):
                value = h.old.e45.previous.restore(source/'checkpoint', 71)
                cursor = read_json(source/'checkpoint/summary.json')['cursor']
                delivered = submit(a, value, word+'。', intensity=.5, source='transcription-only')
                _, raw = advance(s, value, cursor, value.engine.time_us+2000000, observe=True)
                write_gzip(path/f'heldout-{item}.json.gz', raw)
                observed = local_process(raw)
                heard.append({'target': word+'。', 'output': head.decode(observed)['text'],
                    'transformer_output': original.decode([observed])[0]['text'], 'input': delivered})
            rows = []
            for file in sorted((WORK/'cases').glob(f's{seed}-*-test-*/result.json')):
                guard(s)
                row = read_json(file)
                with gzip.open(row['process'], 'rt', encoding='utf-8') as stream:
                    raw = json.load(stream)
                output = head.decode(local_process(raw))
                rows.append({k: row[k] for k in ('seed', 'arm', 'stage', 'item', 'perspective', 'target')} |
                    {'output': output['text'], 'scores': output['scores'], 'untrained_features': output['untrained_features']})
            finish(s, path, tick, {'kind': 'linear-transcription', 'seed': seed, 'core_copies': 4,
                'fit_correct': sum(o == r['text'] for o, r in zip(fitted, samples)), 'fit_count': len(samples),
                'heard_tests': heard, 'rows': rows, 'supervision': 'stage0 isolated actual words only; no task-answer labels',
                'input_features': len(head.keys), 'ridge': head.ridge})
            print({'linear_transcriber': seed, 'fit': sum(o == r['text'] for o, r in zip(fitted, samples)),
                'heldout_heard_words': sum(r['output']==r['target'] for r in heard),
                'transformer_heard_words': sum(r['transformer_output']==r['target'] for r in heard)}, flush=True)
    finally:
        s.active_case = None
        s.db.close()


if __name__ == '__main__':
    main()
