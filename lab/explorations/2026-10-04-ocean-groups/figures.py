import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import HERE,WORK,CONTROLS
from lab.tools.ocean_cli import read_json


def build():
    cases=read_json(WORK/'findings.json')['cases'];(HERE/'figures').mkdir(exist_ok=True)
    colors={'core':'#237964','random-shadow':'#9469a3','random-stopped':'#377aa3'}
    fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
    for g in (0,1):
        for control in CONTROLS:
            item=cases.get(f'copy-g{g}-{control}')
            if item is None:continue
            t=item['timeline']
            # The first recorded frame follows a step and may already include food.
            food0=t[-1]['groups']['all']['food']-item['groups']['all']['delta']['food']
            axes[g,0].step([r['t'] for r in t],[r['groups']['all']['physical'] for r in t],where='post',color=colors[control],label=control)
            axes[g,1].plot([r['t'] for r in t],[r['groups']['all']['food']-food0 for r in t],color=colors[control],label=control)
        for j,title in enumerate(('Physical population','New nutrients consumed')):
            axes[g,j].set_title(f'Copied population {g+1}: {title}');axes[g,j].set_xlabel('Seconds after complete-world fork')
            axes[g,j].grid(alpha=.2);axes[g,j].legend()
    fig.suptitle('E35: the same complete population under three controllers')
    fig.savefig(HERE/'figures/group-copies.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
    for g in (0,1):
        for swap in (0,1):
            item=cases.get(f'mixed-g{g}-swap{swap}');ax=axes[g,swap]
            if item is None:continue
            for cohort in ('A','B'):
                control=item['groups'][cohort]['controller'];t=item['timeline']
                ax.step([r['t'] for r in t],[r['groups'][cohort]['physical'] for r in t],where='post',color=colors[control],label=control)
            ax.set_title(f'World {g+1}; assignment {swap+1}');ax.set_xlabel('Simulated seconds');ax.set_ylabel('Bodies remaining')
            ax.grid(alpha=.2);ax.legend()
    fig.suptitle('E36: shared ocean; consumption only across cohorts')
    fig.savefig(HERE/'figures/shared-competition.png',dpi=140);plt.close(fig)


if __name__=='__main__':build()
