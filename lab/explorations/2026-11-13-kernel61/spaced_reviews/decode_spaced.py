"""Run the existing frozen language child with this campaign's resource guard.

This wrapper changes supervision and evidence retention only. It neither
constructs a Core nor changes the shared language model or its computation.
The registered study host supplies resource_check and calls it after teaching.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from threemind_transformer.language_protocol import LanguageCompute,LanguageProtocol
from threemind_transformer.process_guard import OwnedProcessTree


def original(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)


def decode_batch(folder,protocol,windows,head,resource_check,wall_seconds):
    """At most one CUDA attempt and its declared CPU device-failure fallback.

    Host resource failures do not trigger a retry. A caller must retain this
    directory and register a distinct attempt if postprocessing resumes later.
    """
    import psutil
    folder=Path(folder).resolve();head=Path(head).resolve()
    assert not folder.exists() and head.is_file()
    protocol=LanguageProtocol.model_validate(protocol)
    assert protocol.mode=='strict' and protocol.output_model=='qwen'
    assert 1<=len(windows)<=96 and all(len(v)==256 for v in windows)
    assert 0<wall_seconds<=1800 and resource_check()['safe']
    folder.mkdir(parents=True)
    # Only protocol and numerical activity features cross into the model.
    payload={'protocol':protocol.model_dump(),'windows':windows}
    original(folder/'payload.json',payload)
    started=time.monotonic();attempts=[]
    head_hash=hashlib.sha256(head.read_bytes()).hexdigest()
    for ordinal,device in enumerate(('cuda','cpu')):
        remaining=wall_seconds-(time.monotonic()-started)
        if remaining<=0:raise RuntimeError('read-only decoding wall budget; preserve request')
        assert resource_check()['safe']
        policy=LanguageCompute(compute_device=device,memory_mib=6144,wall_seconds=remaining,threads=2)
        request=folder/f'request-{ordinal}.json';report=folder/f'child-result-{ordinal}.json'
        original(request,{'operation':'decode_many','payload':payload,'compute':policy.model_dump(),
            'head':str(head),'checkpoint':None,'output':str(folder/f'unused-output-{ordinal}.safetensors')})
        stopped=None;peak_private=0;peak_rss=0;last_sample=-1.;sample=None
        with (folder/f'stdout-{ordinal}.log').open('xb') as stdout, \
                (folder/f'stderr-{ordinal}.log').open('xb') as stderr, \
                (folder/f'resources-{ordinal}.jsonl').open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8','-m','threemind_transformer.language_compute',
                'child',str(request),str(report)],stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                env=os.environ|{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            tree=OwnedProcessTree(child.pid)
            original(folder/f'host-{ordinal}.json',{'pid':child.pid,'created':psutil.Process(child.pid).create_time(),
                'command':[sys.executable,'-m','threemind_transformer.language_compute','child',str(request),str(report)]})
            try:
                while child.poll() is None:
                    now=time.monotonic()
                    if now-last_sample>=1:
                        last_sample=now;sample=resource_check();rss=tree.sample();private=0
                        for process in tree.known.values():
                            try:
                                if process.is_running():
                                    memory=process.memory_info();private+=getattr(memory,'private',memory.rss)
                            except psutil.NoSuchProcess:pass
                        peak_private=max(peak_private,private);peak_rss=max(peak_rss,rss)
                        json.dump({'elapsed_seconds':now-started,'resources':sample,
                            'private_bytes':private,'rss_bytes':rss},log,sort_keys=True);log.write('\n');log.flush()
                        if not sample['safe']:stopped='campaign host resource reserve'
                        if max(private,rss)>6144*2**20:stopped='decoder process memory budget'
                    if now-started>wall_seconds:stopped='decoder wall budget'
                    if stopped:tree.stop();break
                    time.sleep(.1)
                child.wait(timeout=10)
            finally:
                tree.stop();child.wait(timeout=10)
        assert hashlib.sha256(head.read_bytes()).hexdigest()==head_hash
        result=json.loads(report.read_bytes()) if report.exists() and report.stat().st_size<=16*2**20 else None
        attempt={'device':device,'returncode':child.returncode,'peak_private_bytes':peak_private,
            'peak_rss_bytes':peak_rss,'stopped':stopped,'report_present':result is not None}
        attempts.append(attempt);original(folder/f'attempt-{ordinal}.json',attempt)
        if stopped or result is None:
            original(folder/'failure.json',{'attempts':attempts,'reason':stopped or 'missing child report'})
            raise RuntimeError('read-only decoding stopped; saved Core subjects remain complete')
        if child.returncode==0:
            assert result['status']=='completed' and len(result['windows'])==len(windows)
            result.update(compute_attempts=attempts,elapsed_seconds=time.monotonic()-started,
                fallback_from_initial_conditions=bool(ordinal),head_sha256=head_hash,
                created_engines=0,campaign_resource_reserves_gib=[5,4,5,25])
            original(folder/'result.json',result)
            return result
        if child.returncode!=86 or ordinal:
            original(folder/'failure.json',{'attempts':attempts,'reason':result.get('reason')})
            raise RuntimeError('read-only decoding failed; preserve request and model report')
    raise AssertionError('unreachable')
