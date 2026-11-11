"""Plot registered scores from completed analyses; no dynamics imports."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def plot(parent):
    a = parent/'assay-v1/analysis-v1.json'
    b = parent/'joint-v1/analysis-v1.json'
    assert json.loads((parent/'assay-v1/independent-audit-v1.json').read_bytes())['passed']
    assert json.loads((parent/'joint-v1/independent-audit-v1.json').read_bytes())['passed']
    data = [json.loads(p.read_bytes()) for p in (a,b)]
    keys = [('W','E:spaced','E:strong','E:novelty'), ('initial','new','reversal','return')]
    ticks = [('Weak\nforgetting','Spaced\nretention','Strong\nretention','Novelty\nretention'),
             ('Initial\nlearning','New\nlearning','Rule\nreversal','Return to\nold rule')]
    labels = ['Inverse log','Weight fast','Weight slow','Matched exp. fast','Matched exp. slow']
    fig, axes = plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax, d, kk, xx, title in zip(axes,data,keys,ticks,('A  Local experience (R48a)','B  Whole learners (R48b)')):
        counts = [[r['scores'][k]['passed'] for k in kk] for r in d['summary']]
        ax.imshow(counts, vmin=0, vmax=8, cmap='Blues', aspect='auto')
        ax.set_xticks(range(4),xx,fontsize=10)
        ax.set_yticks(range(5),labels,fontsize=10)
        ax.set_title(title,loc='left',fontsize=13,fontweight='bold',pad=14)
        for i,row in enumerate(counts):
            for j,n in enumerate(row):
                ax.text(j,i,f'{n}/8',ha='center',va='center',color='white' if n>=5 else 'black',fontsize=12)
                if n>=6:
                    ax.add_patch(Rectangle((j-.46,i-.44),.92,.88,fill=False,edgecolor='white',linewidth=2))
        ax.tick_params(length=0)
        for spine in ax.spines.values(): spine.set_visible(False)
    fig.suptitle('Registered pass counts; outlined cells meet the 6-of-8 target',fontsize=12)
    folder = parent/'joint-v1/figures'
    folder.mkdir(exist_ok=True)
    files = []
    for ext in ('png','svg','pdf'):
        p = folder/('r48-registered-results.'+ext)
        assert not p.exists()
        fig.savefig(p,dpi=180,bbox_inches='tight')
        files.append(dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    plt.close(fig)
    manifest = dict(inputs={str(p.relative_to(parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a,b)},
                    files=files,scope='Selected R48a goals and all R48b goals. Separate sets of eight origins; complete criteria and remaining R48a goals are in the reports.')
    with (folder/'manifest.json').open('x',encoding='utf8') as f:
        json.dump(manifest,f,indent=2)
    print(json.dumps(manifest))


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,required=True)
    plot(p.parse_args().work)
