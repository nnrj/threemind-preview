"""Figures from completed E53 measurements only; no rerun or feedback."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / '.work/ocean-communication-20261006'


def main():
    data = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
    cases = {c['case']: c for c in data['cases']}
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                         'font.size': 11, 'figure.facecolor': '#f1f6f3', 'axes.facecolor': 'white'})
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8))
    modes, labels = ('live', 'muted', 'scrambled'), ('听见同伴', '屏蔽同伴', '打乱同伴频带')
    for axis, field, title in zip(axes.flat, ('new_food', 'new_captures', 'new_births'),
                                  ('40秒内摄入营养颗数', '40秒内完成吞食次数', '40秒内出生数')):
        maximum = 0
        for source, color in ((0, '#167d73'), (1, '#a26aaf')):
            values = [cases[f's{source}-{mode}'][field] for mode in modes]
            maximum = max(maximum, *values)
            axis.plot(labels, values, marker='o', color=color, label=f'环境 {source + 1}')
            for x, y in enumerate(values):
                axis.annotate(str(int(y)), (x, y), xytext=(5, -16 if source == 0 and y > 0 else 8), textcoords='offset points')
        axis.set_title(title)
        axis.set_ylim(0, max(1, maximum) * 1.2)
        axis.grid(axis='y', alpha=.18)
    axes[0, 0].legend(frameon=False)
    axis = axes[1, 1]
    for source, color, offset in ((0, '#167d73', -.16), (1, '#a26aaf', .16)):
        selected = {c['b']: c['mean_action_difference'] for c in data['contrasts']
                    if c['source'] == source and c['a'] == 'live' and c['seconds'] == 1}
        names = ('muted', 'scrambled', 'target', 'matched', 'rescue')
        axis.bar([i + offset for i in range(len(names))], [selected[n] for n in names],
                 width=.3, color=color)
    axis.set_xticks(range(5), ['屏蔽声', '乱频带', '听觉边', '匹配边', '解除屏蔽'])
    axis.set_ylabel('相对正常组的平均动作差')
    axis.set_title('首1秒：同起点个体的动作变化')
    axis.grid(axis='y', alpha=.18)
    fig.suptitle('E53：信号影响、生态结果与连接干预', fontsize=18, y=.99)
    fig.text(.02, .018, '两种完整海洋环境；曲线连接的是对照条件，不是时间。动作差是三维动作向量的距离，不是能力评分。', fontsize=10)
    fig.tight_layout(rect=(0, .045, 1, .96))
    fig.savefig(WORK / 'summary.png', dpi=160)
    fig.savefig(WORK / 'summary.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
