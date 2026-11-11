"""Export /4 replays and a four-arm index; retain the r3 replay edition."""
import argparse
import html
import json
from pathlib import Path

from analyze_four import ARMS, fixed
from replay import LABELS, STAGES, NAMES, export_arm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, default=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
    args = parser.parse_args()
    work = args.work.resolve()
    if not (work/'computation-complete-r4.json').exists():
        raise ValueError('four-arm computation incomplete')
    receipts = [export_arm(work, arm, args.ffmpeg) for arm in ARMS]
    lines = ['<!doctype html><meta charset="utf-8"><title>E67 四组形色实验回放</title>',
        '<style>body{font:18px system-ui;margin:40px;color:#153f38;background:#eff5f2}a{color:#147e68}li{margin:12px}</style>',
        '<h1>E67 · 三版内核、四组形色教学与测试</h1>',
        '<p>协议第4版。完整保留初教、三轮纠错／复习、校准摘要与各轮问答，最后为新位置测试。',
        '视频由原始记录生成，不重新运行意识。各阶段倍速写在画面内；全部采样帧见 HTML。</p>']
    for arm in ARMS:
        lines.extend([f'<h2>{html.escape(LABELS[arm])}</h2>',
                      f'<video controls preload="metadata" width="960" style="max-width:100%" src="{arm}/replay.mp4"></video>',
                      f'<p><a href="{arm}/replay.mp4">打开 MP4</a></p><ul>'])
        lines.extend(f'<li><a href="{arm}/{stage}.html">{NAMES[stage]}</a></li>' for stage in STAGES)
        lines.append('</ul><p>外设校准摘要（不是正式成绩）：')
        lines.extend(f'<a href="{arm}/{fit}.png">{fit}</a> · ' for fit in ['initial-fit', 'fit-1', 'fit-2', 'fit-3'])
        lines.append('</p>')
    fixed(work/'replays/index-four.html', '\n'.join(lines).encode('utf-8'))
    fixed(work/'replays/four-arm-export.json', json.dumps(dict(protocol_revision=4, core_advanced=False,
        index='replays/index-four.html', videos=[dict(arm=r['arm'], video=r['video'],
            sha256=r['sha256'], duration_s=r['duration_s'], clips=r['clips']) for r in receipts]),
        ensure_ascii=False, indent=2).encode('utf-8'))
    print(json.dumps([dict(arm=r['arm'], duration_s=r['duration_s']) for r in receipts]), flush=True)


if __name__ == '__main__':
    main()
