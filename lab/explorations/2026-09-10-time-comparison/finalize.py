"""Preserve the stopped experiment and plot existing evidence; no model execution."""
import gzip
import hashlib
import json
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from run import HERE,WORK,META,Database,Settings,resources,old_inventory,save,capture_implementation
from analyze import read


def main():
    meta=json.loads(META.read_bytes())
    partial=WORK/'dialogue-41701-legacy-no_input.jsonl.gz'
    rows=[]; problem=None
    try:
        with gzip.open(partial,'rt',encoding='utf-8') as stream:
            for line in stream: rows.append(json.loads(line))
    except (EOFError,json.JSONDecodeError,OSError) as exc:
        problem=type(exc).__name__+': '+str(exc)
    # Preserve the original truncated gzip, and provide a separately identified
    # recovered prefix. It is not a reconstructed end-state or complete trial.
    save(HERE/'partial-prefix.json',dict(original_file=partial.name,
        original_sha256=hashlib.sha256(partial.read_bytes()).hexdigest(),error=problem,rows=rows))
    trained=read(WORK/'dialogue-41701-legacy-trace.jsonl.gz')
    with gzip.open(WORK/'dialogue-41701-legacy-trained.json.gz','rb') as stream:
        checkpoint=json.load(stream)
    assert len(trained)==1600 and trained[-1]['tick']==1600
    assert checkpoint['tick']==1600 and len(checkpoint['stimuli'])==200
    # No mutable state reconstruction or continued execution is done here.
    stop=dict(status='stopped_at_resource_limit',reason='legacy dialogue subprocess exceeded 180 wall seconds',
      completed_training_cases=['pair-41701-legacy','pair-41701-current'],
      partial=dict(case='dialogue-41701-legacy',training_inputs=200,training_epochs=1600,
                   checkpoint_intact=True,nodes=len(checkpoint['nodes']),edges=len(checkpoint['edges']),
                   no_input_valid_samples=len(rows),no_input_through_us=rows[-1]['time_us'],
                   duration_seconds=(rows[-1]['time_us']-160_000_000)/1e6,compressed_stream_complete=False,
                   all_nodes_active_at_last=rows[-1]['active']==len(rows[-1]['nodes']),
                   last_mean_activation=rows[-1]['total']/len(rows[-1]['nodes']),last_spread=rows[-1]['spread']),
      not_started=['dialogue-41701-current','pair-41702-legacy','pair-41702-current',
                   'dialogue-41702-legacy','dialogue-41702-current'],
      not_completed=['dialogue-41701-legacy/no_input remainder','dialogue-41701-legacy/cue'],
      process_exit_verified=True,quota=dict(baseline_used_percent=73,latest_used_percent=74),
      supervisor_note='supervise.py adds process-tree cleanup for future runs; it was not used to rerun the stopped case')
    save(HERE/'stop.json',stop)
    db=Database(Settings.from_env().database_url)
    try:
        current=capture_implementation('native')
        expected=json.loads((HERE/'implementation.json').read_bytes())['current_implementation']
        assert current['source_files']==expected['source_files']
        assert current['native_binary_sha256']==expected['native_binary_sha256']
        assert old_inventory(db)==meta['previous_projects']
        audit=dict(core_source_unchanged=True,native_binary_unchanged=True,previous_projects_unchanged=True,
                   frozen_study_files_unchanged=all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h
                     for n,h in meta['frozen_hashes'].items()),resources=resources(db))
        save(HERE/'verification-prepublish.json',audit)
    finally:db.close()

    fig,axes=plt.subplots(1,3,figsize=(13.5,4),layout='constrained')
    x=np.arange(2)
    axes[0].bar(x-.17,[.9,.241864704],width=.34,label='Legacy V3',color='#c57c3b')
    axes[0].bar(x+.17,[.9,.9],width=.34,label='Current',color='#148b7e')
    axes[0].set(xticks=x,xticklabels=['1 frame','1 + 4 zero frames'],ylabel='Raw activation',
                title='Same environmental epoch')
    axes[0].legend(frameon=False)
    for version,color in [('legacy','#c57c3b'),('current','#148b7e')]:
        data=read(WORK/f'pair-41701-{version}-no_input.jsonl.gz')
        axes[1].plot([(r['time_us']-64_000_000)/1e6 for r in data],
                     [r['total']/len(r['nodes']) for r in data],label=version,color=color)
    axes[1].set(xlim=(0,2),xlabel='Seconds after teaching boundary',ylabel='Mean raw activation',
                title='Paired teaching: no new input')
    axes[1].legend(frameon=False)
    acts=np.array([[n[2] for n in r['nodes']] for r in rows]).T
    view=axes[2].imshow(acts,aspect='auto',origin='lower',extent=[0,8.7,1,145],vmin=0,vmax=1,cmap='viridis')
    axes[2].set(xlabel='Seconds after teaching boundary',ylabel='All nodes in identity order',
                title='Legacy dialogue: PARTIAL 8.7 s')
    fig.colorbar(view,ax=axes[2],label='Raw activation')
    fig.savefig(HERE/'time-comparison.png',dpi=155)
    plt.close(fig)
    print(json.dumps({'partial':stop['partial'],'audit':audit},ensure_ascii=False))


if __name__=='__main__':main()
