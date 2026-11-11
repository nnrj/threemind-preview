"""Small CPU CLI acceptance: real raw frame transport and inference boundary."""
import gzip,subprocess
from common import *
from lab.tools.raw_state_expression import RawStateProjection
from threemind_transformer.development_model import load,save


def main():
    torch.set_num_threads(2);folder=WORK/'verification';folder.mkdir(exist_ok=True)
    meta=read_json(WORK/'models/s223-balanced.json');projection=RawStateProjection(**meta['projection'])
    source=WORK/'cases/bus-s223-continued-item0/process.json.gz'
    with gzip.open(source,'rt',encoding='utf-8') as f:process=json.load(f)
    new_json(folder/'layout.json',projection.to_dict())
    row={'id':'real-probe','process':process}
    (folder/'input.jsonl').write_text(json.dumps(row,ensure_ascii=False)+'\n',encoding='utf-8')
    (folder/'labelled.jsonl').write_text(json.dumps(row|{'text':'not allowed'},ensure_ascii=False)+'\n',encoding='utf-8')
    model,metadata=load(WORK/'models/s223-balanced.safetensors','cpu')
    expected=model.decode(np.asarray([projection.project(process)['values']],dtype=np.float32))[0]
    # Copy for a bound-manifest acceptance test; original learned weights intact.
    bound=folder/'bound-reader.safetensors';save(model,bound,metadata|{'projection':projection.to_dict()})
    wrong=projection.to_dict()|{'channels':list(reversed(projection.channels))}
    new_json(folder/'wrong-layout.json',wrong)
    base=[sys.executable,'-m','lab.tools.expression_calibration','decode','--checkpoint',str(bound),'--device','cpu']
    outcomes=[]
    for name,manifest,input_name in [('valid','layout.json','input.jsonl'),('labels','layout.json','labelled.jsonl'),('layout','wrong-layout.json','input.jsonl')]:
        output=folder/(name+'.jsonl')
        result=subprocess.run(base+['--manifest',str(folder/manifest),'--input',str(folder/input_name),'--output',str(output)],cwd=ROOT,capture_output=True,text=True,timeout=90)
        if name=='valid':
            if result.returncode:raise RuntimeError(result.stderr)
            decoded=json.loads(output.read_text(encoding='utf-8'))
            assert decoded['output']==expected and decoded['device']=='cpu'
        else:
            assert result.returncode!=0 and not output.exists()
            assert ('undeclared data' if name=='labels' else 'layout mismatch') in result.stderr
        outcomes.append({'case':name,'passed':True,'exit_code':result.returncode})
    new_json(HERE/'verification.json',{'cpu_cli':outcomes,'cpu_raw_output':expected,'core_changes':False})
    print({'acceptance':outcomes},flush=True)


if __name__=='__main__':main()
