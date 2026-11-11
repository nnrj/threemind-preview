"""Fixed-head copied-state controls, registered before measuring their results."""
from experiment import *
from lab.tools.connection_controls import cross_domain_masks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=(223, 279), default=223)
    args = parser.parse_args()
    torch.set_num_threads(2)
    s = study()
    a = adapter()
    source = WORK/'cases'/f's{args.seed}-feedback-stage2'
    previous = WORK/'cases'/f's{args.seed}-feedback-stage1'
    info = read_json(source/'result.json')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    head = AdaptiveExpression.restore(source/'expression-2', device=device)
    try:
        value = h.old.e45.previous.restore(source/'checkpoint', 71)
        masks = cross_domain_masks(value.engine.capture_state().to_dict(), a.visual_channels(), a.word_channels([n+'。' for n in NAMES]))
        if masks is None:
            new_json(WORK/f'attribution-unavailable-s{args.seed}.json', {'reason': 'no count matched pathways'})
            return
        new_json(WORK/f'attribution-masks-s{args.seed}.json', masks)
        for intervention in ('normal', 'target', 'matched', 'rescue', 'prior-core'):
            for item in range(4):
                for kind in ('visual', 'description'):
                    path, tick = start(s, f'attribute-s{args.seed}-{intervention}-{item}-{kind}')
                    if tick is None:
                        continue
                    owner = previous if intervention == 'prior-core' else source
                    value = h.old.e45.previous.restore(owner/'checkpoint', 71)
                    cursor = read_json(owner/'checkpoint/summary.json')['cursor']
                    if intervention in ('target', 'matched', 'rescue'):
                        edges = masks['matched' if intervention == 'matched' else 'target']
                        value.engine.intervene(edges=edges, action='silence')
                        if intervention == 'rescue':
                            value.engine.intervene(edges=edges, action='unsilence')
                    _, raw, delivered = ask(s, a, value, cursor, item, kind, 9)
                    write_gzip(path/'process.json.gz', raw)
                    output = head.decode([local_process(raw)])[0]
                    target = NAMES[info['assignment'][item]]+'。'
                    donor_target = NAMES[read_json(previous/'result.json')['assignment'][item]]+'。'
                    finish(s, path, tick, {'kind': 'attribution', 'seed': args.seed, 'intervention': intervention,
                        'item': item, 'perspective': kind, 'target': target, 'prior_target': donor_target,
                        'output': output['text'], 'prompt': delivered,
                        'limitation': 'prior-core exchanges age and history; matched paths approximate weight, not topology'})
            print({'attribution': args.seed, 'condition': intervention}, flush=True)
    finally:
        s.active_case = None
        s.db.close()


if __name__ == '__main__':
    main()
