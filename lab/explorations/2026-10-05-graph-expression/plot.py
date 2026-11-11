from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size':11})
fig,axes=plt.subplots(1,3,figsize=(13,4))
sets=[(['Local (2 sources)','Sensory (1 source)'],[74/80,20/40],['74/80','20/40']),
      (['Intact','Target off','Matched off','Restored'],[1,.5,1,1],['16/16','8/16','16/16','16/16']),
      (['Early reader','Continued reader'],[0,0],['0/40','0/40'])]
titles=['Known referents, early held-out tests','Answers depend on selected connections','Entirely new assignment, frozen readers']
colors=['#178474','#b88045','#568cad','#697280']
for ax,(labels,values,counts),title in zip(axes,sets,titles):
    ax.bar(range(len(values)),values,color=colors[:len(values)])
    ax.set_xticks(range(len(values)),labels,rotation=28,ha='right');ax.set_ylim(0,1.16)
    ax.set_title(title,fontsize=10);ax.spines[['top','right']].set_visible(False)
    for i,(value,count) in enumerate(zip(values,counts)):ax.text(i,value+.025,count,ha='center')
fig.suptitle('E50: local naming, causal controls, and the remaining gap');fig.tight_layout()
fig.savefig(Path(__file__).with_name('outcomes.png'),dpi=160)
