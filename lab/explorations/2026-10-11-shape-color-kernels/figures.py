"""Scientific figures from completed E67 measurements, without simulation."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
import numpy as np

ARMS=('2','3.1')
LABELS=('/2','/3.1')
COLORS=('#275f9b','#b06720')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();work=args.work.resolve();source=work/'analysis/verified-results.json'
    data=json.loads(source.read_bytes());rows=[data['arms'][a] for a in ARMS]
    fontpath=Path('C:/Windows/Fonts/msyh.ttc')
    if fontpath.exists():
        fontManager.addfont(str(fontpath));plt.rcParams['font.family']=FontProperties(fname=str(fontpath)).get_name()
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False})
    out=work/'analysis/figures';out.mkdir(exist_ok=True)
    if any(out.glob('*')):raise ValueError('preserve the existing figure edition; inspect or choose a new edition')
    fig,axes=plt.subplots(1,2,figsize=(13,5.4),layout='constrained')
    for i,(row,label,color) in enumerate(zip(rows,LABELS,COLORS)):
        y=[row['scores'][f'development-{r}']['correct']/72*100 for r in range(4)]
        axes[0].plot(range(4),y,label=label,color=color,marker=('o','s','^','D')[i],linewidth=2)
        for x,value in enumerate(y):
            axes[0].annotate(f'{row["scores"][f"development-{x}"]["correct"]}',(x,value),
                             xytext=(0,6+8*(i%2)),textcoords='offset points',ha='center',fontsize=9,color=color)
        vals=[row['scores']['final'][k]['correct']/row['scores']['final'][k]['n']*100 for k in ('shape','color','pairs')]
        bars=axes[1].bar(np.arange(3)+(i-.5)*.32,vals,width=.30,label=label,color=color)
        for bar,k in zip(bars,('shape','color','pairs')):
            result=row['scores']['final'][k]
            axes[1].text(bar.get_x()+bar.get_width()/2,bar.get_height()+1,
                         f'{result["correct"]}/{result["n"]}',ha='center',va='bottom',rotation=90,fontsize=8)
    axes[0].set(title='开发题：初教与三轮纠错',xticks=range(4),xticklabels=['初教','纠错1','纠错2','纠错3'],ylabel='正确率 (%)',ylim=(0,116))
    axes[1].set(title='最终留出位置：冻结后测试',xticks=range(3),xticklabels=['形状','颜色','形色两问均对'],ylim=(0,122),ylabel='正确率 (%)')
    for ax in axes:ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    axes[0].legend(loc='lower right');fig.suptitle('E67 · /2 与 /3.1 完整系统形色实验\n同一配对训练种子；题目数量不是独立训练重复',fontsize=15)
    fig.savefig(out/'accuracy.png',dpi=150);fig.savefig(out/'accuracy.svg');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4.8),layout='constrained')
    measures=[('core_seconds_per_sim_second','原生 Core 推进','墙钟秒 / 模拟秒'),
              ('restore_s','完整系统恢复累计','墙钟秒'),('wall_s','阶段工作累计（含恢复）','墙钟秒')]
    for ax,(key,title,unit) in zip(axes,measures):
        values=[r[key] for r in rows];bars=ax.bar(LABELS,values,color=COLORS)
        ax.set(title=title,ylabel=unit);ax.tick_params(axis='x',labelrotation=25)
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        for b,v in zip(bars,values):ax.annotate(f'{v:,.2f}',(b.get_x()+b.get_width()/2,v),xytext=(0,4),textcoords='offset points',ha='center',fontsize=9)
        ax.set_ylim(0,max(values)*1.18)
    fig.suptitle('E67 · 计算与恢复分别计量\n原生调用含原生返回编码；阶段用时不含阶段末平台附件同步',fontsize=14)
    fig.savefig(out/'performance.png',dpi=150);fig.savefig(out/'performance.svg');plt.close(fig)
    print(json.dumps({'figures':str(out),'source':str(source)}))


if __name__=='__main__':main()
