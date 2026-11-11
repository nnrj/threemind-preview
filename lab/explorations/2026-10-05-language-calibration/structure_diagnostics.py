"""Read-only graph boundary inspection of existing checkpoints; no evolution."""
import json

from experiment import HERE, WORK, previous, read_json

from lab.tools.service_study import new_json


def main():
    rows=[]
    for parent in sorted((WORK/'cases').glob('*stream-sparse-default-s*-normal')):
        if not parent.name.startswith(('formal-','composition-')):continue
        definition=read_json(parent/'definition.json');seed=definition['seed']
        seconds=532 if definition['stage']=='composition' else 266
        value=previous.restore(parent/f'checkpoint-{seconds}',seed)
        state=value.engine.capture_state().to_dict()
        channels={int(n['id']):int(n['channel']) for n in state['nodes']}
        sensory={c for lib in definition['libraries'].values() for c in lib['channels']}
        counts={'within_declared_senses':0,'between_senses_and_other_channels':0,'within_other_channels':0}
        for e in state['edges']:
            a=channels[int(e['source'])] in sensory;b=channels[int(e['target'])] in sensory
            key='between_senses_and_other_channels' if a!=b else 'within_declared_senses' if a else 'within_other_channels'
            counts[key]+=1
        rows.append({'source':parent.name,'checkpoint_seconds':seconds,'nodes':len(channels),'edges':len(state['edges']),
            'counts':counts,'scope':'declared visual/name/audio channels; other channels include non-name language features and background'})
    new_json(HERE/'structure-diagnostics.json',{'posthoc_readonly':True,'rows':rows,'inference_boundary':'absence of crossing edges isolates these channel sets at this checkpoint; presence alone does not prove transmission'})
    print(json.dumps(rows))


if __name__=='__main__':main()
