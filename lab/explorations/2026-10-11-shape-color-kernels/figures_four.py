"""Four-arm scientific figures from saved measurements, without simulation."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
import numpy as np

ARMS = ('2', '3.1', '4-adaptive', '4-legacy')
LABELS = ('/2', '/3.1', '/4 H', '/4 稳定度')
COLORS = ('#275f9b', '#b06720', '#217864', '#8752a5')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    work = parser.parse_args().work.resolve()
    data = json.loads((work/'analysis-r4/verified-results.json').read_bytes())
    space = json.loads((work/'analysis-r4/storage.json').read_bytes())
    rows = [data['arms'][arm] for arm in ARMS]
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        fontManager.addfont(str(font))
        plt.rcParams['font.family'] = FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.unicode_minus': False})
    out = work/'analysis-r4/figures'
    out.mkdir(exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('preserve existing figures; inspect an interrupted export before retrying')
    def save(fig, name):
        fig.savefig(out/(name+'.png'), dpi=150)
        fig.savefig(out/(name+'.svg'))
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), layout='constrained')
    for i, (row, label, color) in enumerate(zip(rows, LABELS, COLORS)):
        axes[0].plot(range(4), [row['scores'][f'development-{r}']['correct']/72*100 for r in range(4)],
                     label=label, color=color, marker=('o', 's', '^', 'D')[i], linewidth=2)
        values = [row['scores']['final'][k]['correct']/row['scores']['final'][k]['n']*100
                  for k in ('shape', 'color', 'pairs')]
        bars = axes[1].bar(np.arange(3)+(i-1.5)*.21, values, width=.19, label=label, color=color)
        for bar, key in zip(bars, ('shape', 'color', 'pairs')):
            score = row['scores']['final'][key]
            axes[1].text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                         f'{score["correct"]}/{score["n"]}', ha='center', va='bottom', rotation=90, fontsize=8)
    axes[0].set(title='同一开发题：纠错前后', xticks=range(4), xticklabels=['初教', '轮1', '轮2', '轮3'],
                ylabel='正确率 (%)', ylim=(0, 110))
    axes[1].set(title='最终新位置测试', xticks=range(3), xticklabels=['形状', '颜色', '形色两问均对'],
                ylabel='正确率 (%)', ylim=(0, 126))
    for ax in axes:
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    axes[0].legend(loc='lower right')
    fig.suptitle('E67 · 三版内核、四个完整个体\n同一配对训练种子；最终留出为位置，不是全新概念', fontsize=14)
    save(fig, 'accuracy')
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.1), layout='constrained')
    measures = [(lambda r: r['core_seconds_per_sim_second'], '原生推进', '墙钟秒 / 模拟秒'),
                (lambda r: r['restore_s'], '完整恢复累计', '墙钟秒'),
                (lambda r: r['source_graph']['edges'], '教学主线最终连接', '条连接')]
    for ax, (get, title, unit) in zip(axes, measures):
        values = [get(row) for row in rows]
        bars = ax.bar(LABELS, values, color=COLORS)
        ax.set(title=title, ylabel=unit, ylim=(0, max(values)*1.2))
        ax.tick_params(axis='x', labelrotation=25)
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
        for bar, value in zip(bars, values):
            ax.annotate(f'{value:,.2f}', (bar.get_x()+bar.get_width()/2, value), xytext=(0, 5),
                        textcoords='offset points', ha='center', fontsize=8)
    fig.suptitle('计算、恢复与连接规模分列\n原生调用包含返回编码；普通本机串行运行，不是独占硬件微基准', fontsize=13)
    save(fig, 'performance-scale')
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.1), layout='constrained')
    settings = [('all_files', '全部实验文件', 2**30, 'GiB'),
                ('complete_individual', '一个当前完整个体', 2**20, 'MiB'),
                ('core_standalone_gzip_bytes', 'Core单独压缩编码', 2**20, 'MiB')]
    for ax, (key, title, factor, unit) in zip(axes, settings):
        values = [(space['arms'][a][key]['bytes'] if isinstance(space['arms'][a][key], dict)
                   else space['arms'][a][key])/factor for a in ARMS]
        bars = ax.bar(LABELS, values, color=COLORS)
        ax.set(title=title, ylabel=unit, ylim=(0, max(values)*1.2))
        ax.tick_params(axis='x', labelrotation=25)
        for bar, value in zip(bars, values):
            ax.annotate(f'{value:.2f}', (bar.get_x()+bar.get_width()/2, value), xytext=(0, 5),
                        textcoords='offset points', ha='center', fontsize=9)
    fig.suptitle('文件逻辑字节；完整个体包含外设学习状态与身体\n公共文件只计一次；数据库共享页不按模型强行摊分，Core-only不代表完整个体', fontsize=13)
    save(fig, 'storage')
    print(json.dumps({'figures': str(out)}), flush=True)


if __name__ == '__main__':
    main()
