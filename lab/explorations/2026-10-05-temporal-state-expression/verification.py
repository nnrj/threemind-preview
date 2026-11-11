"""Focused observation and tool-contract checks, not a mass evidence rehash."""
import subprocess
import numpy as np
from experiment import *
from raw_analysis import load_process
from lab.tools.raw_state_expression import RawStateProjection,RawGraphStateProjection,load_graph_expression
from threemind_transformer.development_model import load


def main():
    torch.set_num_threads(2)
    checks={};new=WORK/'cases/graph-s223-continued-t532-item0-v9-i0.5-test/process.json.gz'
    choices=list((OLD/'cases').glob('s223-continued-t532-words0-v9-i0.5-test-none/process.json.gz'))
    if not choices:raise RuntimeError('known old probe missing')
    previous=load_process(choices[0]);current=load_process(new)
    def recorded(p):
        return [(f['time_us'],[{k:n[k] for k in ('id','channel','activation','inhibition','trace','support','stability')}
            for n in f['nodes']]) for f in p['trajectory']]
    if recorded(previous)!=recorded(current):raise AssertionError('new full-state observer changed the old process')
    checks['one_unchanged_probe_with_full_state_capture']=True
    folder=WORK/'verification';folder.mkdir(exist_ok=True)
    for kind,receipt in (('raw',WORK/'raw-models/223-words-history-all.json'),('graph',WORK/'graph-models/223-graph.json')):
        r=read_json(receipt)
        projection=(RawGraphStateProjection if kind=='graph' else RawStateProjection)(**r['projection'])
        checkpoint=receipt.with_suffix('.safetensors')
        model,_=(load_graph_expression if kind=='graph' else load)(checkpoint,'cpu')
        values=projection.project(current)
        if kind=='raw':values=values['values']
        expected=model.decode(np.asarray([values],dtype=np.float32))[0]['text']
        new_json(folder/f'{kind}-layout.json',projection.to_dict())
        with (folder/f'{kind}-input.jsonl').open('x',encoding='utf-8') as f:f.write(encoded({'id':'contract','process':current}).decode()+'\n')
        subprocess.run([sys.executable,'-m','lab.tools.raw_state_expression','--manifest',str(folder/f'{kind}-layout.json'),
            '--input',str(folder/f'{kind}-input.jsonl'),'--output',str(folder/f'{kind}-output.jsonl'),
            '--checkpoint',str(checkpoint),'--device','cpu'],check=True)
        actual=read_json(folder/f'{kind}-output.jsonl')
        if actual['output']['text']!=expected:raise AssertionError('CLI/model projection mismatch')
        checks[kind+'_cpu_cli_round_trip']=True
    new_json(HERE/'verification.json',checks);print(checks)


if __name__=='__main__':main()
