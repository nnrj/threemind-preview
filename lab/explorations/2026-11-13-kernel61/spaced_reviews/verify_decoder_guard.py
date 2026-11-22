"""Isolated supervisor checks with fake children; no model or Core is loaded."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import decode_spaced as d
import materials_spaced as m


def check(output):
    assert not output.exists();output.mkdir(parents=True)
    head=output/'fake-head.safetensors';head.write_bytes(b'isolated-supervisor-fixture')
    outcomes=[]
    for scenario in ('success','device-fallback','host-reserve','process-memory','missing-report'):
        children=[];resource_calls=0
        def resources():
            nonlocal resource_calls
            resource_calls+=1
            return {'safe':not(scenario=='host-reserve' and resource_calls>=3)}
        class Child:
            def __init__(self,command,**kwargs):
                self.pid=os.getpid();self.killed=False
                request=json.loads(Path(command[-2]).read_bytes())
                assert set(request['payload'])=={'protocol','windows'}
                assert request['payload']['windows']==[[0.]*256]
                assert kwargs['creationflags']==getattr(d.subprocess,'CREATE_NO_WINDOW',0)
                ordinal=len(children);children.append(self)
                self.returncode=(86 if scenario=='device-fallback' and ordinal==0 else
                    None if scenario in ('host-reserve','process-memory') else 0)
                if scenario!='missing-report':
                    Path(command[-1]).write_text(json.dumps({'status':'device_failed' if self.returncode==86 else 'completed',
                        'windows':[{'text':'fixture'}],'reason':'isolated device fixture'}),encoding='utf-8')
            def poll(self):return self.returncode
            def wait(self,timeout):assert self.returncode is not None;return self.returncode
        class Tree:
            def __init__(self,pid):
                class RetiredProcess:
                    def is_running(self):return False
                    def memory_info(self):raise AssertionError('must not sample a retired process identity')
                assert pid==os.getpid();self.child=children[-1];self.known={0:RetiredProcess()}
            def sample(self):return 7*2**30 if scenario=='process-memory' else 1
            def stop(self):
                self.child.killed=True
                if self.child.returncode is None:self.child.returncode=-9
        folder=output/scenario
        with patch.object(d.subprocess,'Popen',Child),patch.object(d,'OwnedProcessTree',Tree):
            failed=False
            try:result=d.decode_batch(folder,m.protocol(17).model_dump(),[[0.]*256],head,resources,30)
            except RuntimeError:failed=True
        expected_fail=scenario in ('host-reserve','process-memory','missing-report')
        assert failed==expected_fail and all(v.killed for v in children)
        assert len(children)==(2 if scenario=='device-fallback' else 1)
        if failed:
            assert (folder/'failure.json').exists() and not (folder/'result.json').exists()
        else:
            assert result['created_engines']==0 and result['fallback_from_initial_conditions']==(scenario=='device-fallback')
        outcomes.append({'scenario':scenario,'passed':True,'fake_attempts':len(children),'failure_preserved':failed})
    proof={'passed':True,'created_engines':0,'loaded_models':0,'spawned_processes':0,'cases':outcomes,
        'source_sha256':m.sha(Path(d.__file__))}
    d.original(output/'proof.json',proof)
    print(json.dumps(proof),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    check(parser.parse_args().output.resolve())
