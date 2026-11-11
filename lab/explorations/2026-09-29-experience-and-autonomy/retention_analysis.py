"""Read-only analyses of the registered 80-copy retention extension."""
import json
from analyze import net,subtract,save
from common import WORK
from experiment import SEEDS,gzread,symbols
from retention_extension import PROTOCOLS,CONDITIONS

def main():
    output=[];structures=[]
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            for condition in CONDITIONS:
                prefix=f'retention-extension/s{seed}/{protocol}/{condition}'
                base=f'retention-extension/s{seed}/none/{condition}'
                a=net(prefix+'/A',prefix+'/none',seed)
                b=net(base+'/A',base+'/none',seed)
                output.append({'seed':seed,'protocol':protocol,'condition':condition,'net':a,
                               'no_training_net':b,'training_effect':subtract(a,b)})
            for age,part in ((1,'train'),(30,'age30'),(300,'age300')):
                state=gzread(WORK/'cases'/f'memory/s{seed}/{protocol}/{part}/parent-state.json.gz')
                nodes={n['channel']:n for n in state['nodes']};ids={k:nodes.get(ch,{}).get('id') for k,ch in symbols(seed).items()}
                selected={}
                for pair in ('AB','AD','BA','DA'):
                    edge=next((e for e in state['edges'] if (e['source'],e['target'])==(ids[pair[0]],ids[pair[1]])),None)
                    selected[pair]=edge
                structures.append({'seed':seed,'protocol':protocol,'age_s':age,'edges':selected,
                    'nodes':{k:nodes.get(ch) for k,ch in symbols(seed).items()}})
    value={'rows':output,'structural_snapshots':structures}
    save('retention-extension-analysis.json',value)
    print(json.dumps([r for r in output if r['protocol'] in ('spaced_ordinary','spaced_no_consolidation')]),flush=True)

if __name__=='__main__':main()
