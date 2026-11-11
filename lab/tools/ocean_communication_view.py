"""Portable full-habitat replay with measured acoustic links; no simulation."""
import argparse
import base64
import gzip
import json
from pathlib import Path


def case_label(name):
    if len(name) < 4 or name[:3] not in ('s0-', 's1-'):
        return name
    labels = {'development-00': '培养：0～20秒', 'development-01': '培养：20～150秒',
              'live': '正常听觉', 'muted': '屏蔽同伴声音', 'scrambled': '打乱同伴频带',
              'target': '屏蔽听觉连接', 'matched': '屏蔽匹配连接', 'rescue': '解除听觉连接屏蔽',
              'matched-resume': '屏蔽匹配连接（暂停后继续）',
              'muted-target': '屏蔽同伴声音与听觉连接', 'muted-matched': '屏蔽同伴声音与匹配连接',
              'early-live': '早期：正常听觉', 'early-muted': '早期：屏蔽同伴声音',
              'joint-development': '共同采样 /2：0～30秒', 'joint-muted': '共同采样 /2：屏蔽同伴'}
    return f"环境{int(name[1]) + 1} · {labels.get(name[3:], name[3:])}"


def build(cases, output):
    recordings = []
    for path in map(Path, cases):
        protocol = json.loads((path / 'protocol.json').read_bytes())
        if protocol['schema'] not in ('threemind.ocean-communication/1', 'threemind.ocean-communication/2'):
            raise ValueError('communication recording required')
        with gzip.open(path / 'trajectory.jsonl.gz', 'rt', encoding='utf-8') as f:
            frames = [json.loads(line) for line in f]
        frames.append(json.loads((path / 'result.json').read_bytes()))
        sound = {}
        with gzip.open(path / 'communication.jsonl.gz', 'rt', encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                key = row['time_us'] // 200000
                # Display all observed sources in this 200ms bin, not invented links.
                item = sound.setdefault(key, {'links': set(), 'bands': {}})
                for receiver in row['received']:
                    for packet in receiver['packets']:
                        if packet['sender'] != packet['receiver']:
                            item['links'].add((packet['sender'], packet['receiver']))
                    item['bands'][receiver['individual']] = receiver['power']
        packed = []
        for frame in frames:
            stamp = frame['time_us']
            s = sound.get(stamp // 200000, {'links': [], 'bands': {}})
            packed.append({'time_us': stamp, 'food': frame['food_positions'],
                           'members': [{k: m[k] for k in ('id', 'parent', 'generation', 'cohort', 'position', 'radius',
                                                         'elongation', 'angle', 'physical', 'grains', 'captured', 'storage')}
                                       for m in frame['members']],
                           'links': sorted(s['links']), 'bands': s['bands'], 'sound': frame['communication']})
        recordings.append({'name': path.name, 'label': case_label(path.name), 'protocol': protocol, 'frames': packed})
    # Lossless browser-native decompression avoids publishing a second huge
    # uncompressed copy of the complete-world observations.
    raw = json.dumps(recordings, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    payload = json.dumps(base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode('ascii'))
    template = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        f.write(template.replace('/*PACKED_RECORDINGS*/""', payload))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--case', type=Path, action='append', required=True)
    a = p.parse_args()
    build(a.case, a.output)
