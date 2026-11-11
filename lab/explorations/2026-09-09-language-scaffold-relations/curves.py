"""Fixed first-seed illustration, never pick a successful example after the fact."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run import HERE, META, WORK, encoded
from threemind_lab import calibration
from threemind_lab.config import Settings
from threemind_lab.database import Database

meta=json.loads(META.read_bytes())
data=json.loads((WORK/meta['completed_phases']['main']).read_bytes())
case=next(c for c in data['rows'] if c['seed']==41601 and c['arm']=='full')
db=Database(Settings.from_env().database_url)
try:
    result=calibration.result(db,meta['project_id'],case['measurements']['family']['id'])
finally:
    db.close()
sham=next(r for r in result['rows'] if not r['cue'])
probes=[next(r for r in result['rows'] if r['cue']==q) for q in ['Z的爷爷是谁？','W的爷爷是谁？']]
fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True,constrained_layout=True)
for i,row in enumerate(probes):
    times=[p['offset_us']/1e6 for p in row['curve']]
    axes[0].plot(times,[p['saturated_fraction'] for p in row['curve']],label=['Grandfather of Z?','Grandfather of W?'][i])
    for word,color in zip(['X','Y','U','V'],['#237e74','#a77530','#5772a5','#ab634a']):
        values=[p['terms'][word]-b['terms'][word] if p['terms'][word] is not None else float('nan')
                for p,b in zip(row['curve'],sham['curve'])]
        axes[i+1].plot(times,values,label=word,color=color)
    axes[i+1].set_ylabel(f"Query {'Z' if i==0 else 'W'}\nNet term projection")
axes[0].set_ylabel('Fraction at saturation')
axes[0].set_ylim(-.02,1.02)
for ax in axes:
    ax.axvspan(.2,1,color='grey',alpha=.07)
    ax.legend(loc='upper left',ncol=4)
    ax.grid(alpha=.2)
axes[-1].set_xlabel('Simulated seconds after query; shaded = declared score window')
fig.suptitle('Fixed example: seed 41601, full teaching, birth clone')
fig.savefig(HERE/'time-courses.png',dpi=160)
plt.close(fig)
(HERE/'time-courses.json').write_bytes(encoded({'seed':41601,'arm':'full','selection':'first preregistered seed',
                                              'source_hash':result['source_hash'],'rows':probes,'sham':sham}))
print('Fixed representative curves saved.')
