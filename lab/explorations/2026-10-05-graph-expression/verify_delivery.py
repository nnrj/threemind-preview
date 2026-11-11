"""Final external-tool acceptance on existing evidence; no new Core cases."""
import subprocess
from common import *
from threemind_transformer.local_activity import local_process as delivered
from local_activity import local_process as measured
from threemind_transformer.graph_expression import load


def main():
    torch.set_num_threads(2)
    folder=WORK/'acceptance';folder.mkdir(exist_ok=True)
    source=read_json(WORK/'models/multi-s223-local.json')
    paths=source['training_cases'][:2]
    raw=[process(p) for p in paths]
    assert all(delivered(p)==measured(p) for p in raw)
    rows=[{'id':str(i),'process':p} for i,p in enumerate(raw)]
    for name,data in [('raw',rows),('teaching',[dict(r,text=source['training_labels'][i]) for i,r in enumerate(rows)]),
                      ('invalid',[dict(rows[0],text='forbidden inference label')])]:
        with (folder/f'{name}.jsonl').open('x',encoding='utf-8') as f:
            for r in data:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    checkpoint=WORK/'models/multi-s223-local.safetensors'
    commands=[['config'],['prepare','--input','raw.jsonl','--output','prepared.jsonl'],
        ['decode','--input','raw.jsonl','--output','cpu.jsonl','--checkpoint',checkpoint,'--device','cpu'],
        ['decode','--view','prepared-local','--input','prepared.jsonl','--output','auto.jsonl','--checkpoint',checkpoint],
        ['train','--input','teaching.jsonl','--output','continued.safetensors','--checkpoint',checkpoint,'--steps','1','--device','cpu']]
    logs=[]
    for args in commands:
        result=subprocess.run([sys.executable,'-m','threemind_transformer.graph_expression_cli',*map(str,args)],cwd=folder,
                              capture_output=True,text=True,encoding='utf-8',check=True)
        logs.append({'args':list(map(str,args)),'stdout':result.stdout,'stderr':result.stderr})
    invalid=subprocess.run([sys.executable,'-m','threemind_transformer.graph_expression_cli','decode','--input','invalid.jsonl',
        '--output','invalid-output.jsonl','--checkpoint',str(checkpoint)],cwd=folder,capture_output=True,text=True,encoding='utf-8')
    assert invalid.returncode!=0 and not (folder/'invalid-output.jsonl').exists()
    cpu=[json.loads(line) for line in (folder/'cpu.jsonl').read_text(encoding='utf-8').splitlines()]
    auto=[json.loads(line) for line in (folder/'auto.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [r['output'] for r in cpu]==[r['output'] for r in auto]
    old,_=load(FIRST/'models/graph-base.safetensors','cpu') if (FIRST/'models/graph-base.safetensors').exists() else (None,None)
    old_paths=list((FIRST/'models').glob('*.safetensors'))
    if old is None:
        assert old_paths
        old,_=load(old_paths[0],'cpu')
    assert old.config.schema=='threemind.graph-expression/1'
    new_json(folder/'verification.json',{'local_projection_exact_parity':True,'cpu_and_auto_decode_equal':True,
        'old_checkpoint_load':old.config.schema,'continued_training_new_file':True,
        'inference_labels_rejected':True,'commands':logs,'cpu_outputs':cpu})
    print({'acceptance':'passed','cpu_auto':[r['output']['text'] for r in cpu]},flush=True)


if __name__=='__main__':main()
