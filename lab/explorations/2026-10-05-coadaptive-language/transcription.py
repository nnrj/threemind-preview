"""Stricter peripheral: teach words, never object-name answers."""
from experiment import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=(223, 279), default=223)
    args = parser.parse_args()
    torch.set_num_threads(2)
    s = study()
    a = adapter()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    head = AdaptiveExpression(device=device)
    initial = None
    try:
        s.allow_extension()
        for stage in (0, 1, 2):
            source = WORK/'cases'/f's{args.seed}-feedback-stage{stage}'
            if not (source/'result.json').exists():
                break
            case, tick = start(s, f'transcription-s{args.seed}-stage{stage}')
            if tick is None:
                if read_json(case/'result.json')['fit_correct'] < 7:
                    break
                head = AdaptiveExpression.restore(case/'expression', device=device)
                if stage == 0:
                    initial = AdaptiveExpression.restore(case/'expression', device=device)
                continue
            if (s.completed_count or 0) + s.extra_core_copies + 8 > s.settings.instance_limit:
                raise RuntimeError('eight calibration copies exceed budget')
            samples = []
            for item, word in enumerate(NAMES):
                for intensity in (.4, .6):
                    value = h.old.e45.previous.restore(source/'checkpoint', 71)
                    cursor = read_json(source/'checkpoint/summary.json')['cursor']
                    delivered = submit(a, value, word+'。', intensity=intensity, source='transcription-only')
                    _, raw = advance(s, value, cursor, value.engine.time_us+2000000, observe=True)
                    file = case/f'{item}-{intensity}.json.gz'
                    write_gzip(file, raw)
                    process = local_process(raw)
                    receipt = f's{args.seed}-stage{stage}-word{item}-intensity{intensity}'
                    head.teach(process, word+'。', receipt=receipt)
                    samples.append({'process': process, 'text': word+'。', 'input': delivered})
            head.adapt(case/'expression', steps=1500 if stage == 0 else 1000, check=lambda: guard(s))
            fitted = head.decode([r['process'] for r in samples])
            if stage == 0:
                initial = AdaptiveExpression.restore(case/'expression', device=device)
            rows = []
            for path in sorted((WORK/'cases').glob(f's{args.seed}-*-stage{stage}-test-*/result.json')):
                probe = read_json(path)
                with gzip.open(probe['process'], 'rt', encoding='utf-8') as f:
                    process = local_process(json.load(f))
                rows.append({'item': probe['item'], 'source_arm': probe['arm'], 'perspective': probe['perspective'], 'target': probe['target'],
                    'adaptive_output': head.decode([process])[0]['text'],
                    'frozen_output': initial.decode([process])[0]['text'], 'original_process': probe['process']})
            correct = sum(o['text'] == r['text'] for o, r in zip(fitted, samples))
            finish(s, case, tick, {'kind': 'transcription', 'seed': args.seed, 'stage': stage,
                'fit_correct': correct, 'fit_count': 8, 'rows': rows,
                'supervision': 'isolated actual words only; no object-name assignments',
                'core_copies': 8, 'training_inputs': [r['input'] for r in samples]})
            print({'transcription': args.seed, 'stage': stage, 'fit': f'{correct}/8',
                'test_main': f"{sum(r['adaptive_output']==r['target'] for r in rows if r['item']>=0 and r['source_arm']=='feedback')}/{sum(r['item']>=0 and r['source_arm']=='feedback' for r in rows)}"}, flush=True)
            if correct < 7:
                print({'stopped': 'transcription calibration below 7/8; later stages untested'}, flush=True)
                break
    finally:
        s.active_case = None
        s.db.close()


if __name__ == '__main__':
    main()
