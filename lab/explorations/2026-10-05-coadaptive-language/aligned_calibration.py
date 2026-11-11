"""Context-balanced diagnosis, explicitly answer-supervised, not pure translation."""
from experiment import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=(223, 279), default=223)
    args = parser.parse_args()
    torch.set_num_threads(2)
    s = study()
    a = adapter()
    source = WORK/'cases'/f's{args.seed}-feedback-stage2'
    info = read_json(source/'result.json')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    original = AdaptiveExpression.restore(source/'expression-2', device=device)
    head = AdaptiveExpression.restore(source/'expression-2', device=device)
    try:
        s.allow_extension()
        path, tick = start(s, f'aligned-s{args.seed}-calibration')
        if tick is not None:
            if (s.completed_count or 0) + s.extra_core_copies + 8 > s.settings.instance_limit:
                raise RuntimeError('eight calibration copies exceed budget')
            samples = []
            for item in range(4):
                for kind in ('visual', 'description'):
                    value = h.old.e45.previous.restore(source/'checkpoint', 71)
                    cursor = read_json(source/'checkpoint/summary.json')['cursor']
                    _, raw, delivered = ask(s, a, value, cursor, item, kind, 8)
                    write_gzip(path/f'{item}-{kind}.json.gz', raw)
                    target = NAMES[info['assignment'][item]]+'。'
                    observed = local_process(raw)
                    head.teach(observed, target, receipt=f'aligned-s{args.seed}-{item}-{kind}')
                    samples.append({'process': observed, 'text': target, 'prompt': delivered})
            head.adapt(path/'expression', steps=1000, check=lambda: guard(s))
            out = head.decode([r['process'] for r in samples])
            finish(s, path, tick, {'kind': 'aligned-calibration', 'seed': args.seed, 'core_copies': 8,
                'fit_correct': sum(o['text'] == r['text'] for o, r in zip(out, samples)), 'fit_count': 8,
                'inputs': [r['prompt'] for r in samples], 'supervision': 'object answers; diagnostic, not pure translator'})
        else:
            head = AdaptiveExpression.restore(path/'expression', device=device)
        for item in range(4):
            for kind in ('visual', 'new-paraphrase', 'new-relation'):
                test, tick = start(s, f'aligned-s{args.seed}-test-{item}-{kind}')
                if tick is None:
                    continue
                value = h.old.e45.previous.restore(source/'checkpoint', 71)
                cursor = read_json(source/'checkpoint/summary.json')['cursor']
                if kind == 'visual':
                    text = question(item, 'visual')
                elif kind == 'new-paraphrase':
                    text = f'{COLORS[item]}{SHAPES[item]}的名字是什么？'
                else:
                    text = f'与{WORDS[item ^ 2]}颜色相同的{SHAPES[item]}，名字是什么？'
                delivered = submit(a, value, text, item=item if kind == 'visual' else None, view=11,
                                   intensity=.5, source='question')
                _, raw = advance(s, value, cursor, value.engine.time_us+2000000, observe=True)
                write_gzip(test/'process.json.gz', raw)
                observed = local_process(raw)
                finish(s, test, tick, {'kind': 'aligned-test', 'seed': args.seed, 'item': item, 'perspective': kind,
                    'target': NAMES[info['assignment'][item]]+'。', 'original_output': original.decode([observed])[0]['text'],
                    'output': head.decode([observed])[0]['text'], 'prompt': delivered})
        print({'aligned': args.seed, 'complete': True}, flush=True)
    finally:
        s.active_case = None
        s.db.close()


if __name__ == '__main__':
    main()
