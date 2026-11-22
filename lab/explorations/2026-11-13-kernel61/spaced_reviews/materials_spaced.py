"""Pure E43 curriculum and artifact inventory; no Core or decoder is created."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.spaced_reviews import schedule
from threemind_transformer.language_protocol import LanguageProtocol
from threemind_transformer.language_senses import embedding_frame

OLD=ROOT/'.work/language-spaced-20261004'
SEEDS=(17,29)
CORE_SEED=20260724
CONDITIONS=('spaced','reversed','massed','frozen','untaught')
NAMES=('甲','乙','丁','戊')
WORDS=('松子','铃铛','陶杯','柳叶')
CHECKPOINTS=(24,48,80,144,272,528,530,590,830)
PROBES=(24,144,530,590,830)


def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol(seed):
    return LanguageProtocol(input_model='qwen',output_model='qwen',mode='strict',seed=seed,
        response_us=500000,feature_bins=4,feature_buckets=64,embedding_dimensions=64,maximum_tokens=24)


def inventory():
    assets=read(OLD/'assets.json');rows=[];source_checkpoints=[]
    background=[json.loads(line) for line in (OLD/'physical-telemetry.jsonl').read_bytes().splitlines()]
    assert len(background)==1682 and max(int(v['time_us']) for v in background)>=833000000
    bg_channels={ch for v in background if v['stimulus'] for ch,_ in v['stimulus']['channels']}
    raw_sources=[]
    for seed in SEEDS:
        mapping=protocol(seed)
        mask=int.from_bytes(hashlib.blake2s(f'language-input/1:{seed}'.encode(),digest_size=4).digest(),'big')
        assert not bg_channels&{mask^i for i in range(128)}
        assert Counter(v['label'] for v in assets['calibration'][str(seed)])==dict.fromkeys(WORDS,4)
        for condition in CONDITIONS:
            key=f's{seed}-{condition}';folder=OLD/'cases'/key
            definition=read(folder/'definition.json');old=read(folder/'result.json')
            assert definition['protocol']==mapping.model_dump()
            assert definition['config']['seed']==CORE_SEED and old['life']=='active'
            labels=WORDS[::-1] if condition=='reversed' else WORDS
            texts=[name+'是'+word+'。' for name,word in zip(NAMES,labels)]
            mode='none' if condition=='untaught' else 'massed' if condition=='massed' else 'spaced'
            lessons=schedule(texts,seed,mode)
            assert lessons==definition['lessons']
            expected={} if mode=='none' else dict.fromkeys(texts,57)
            assert Counter(v['text'] for v in lessons)==expected
            frames=[{'time_us':v['time_us'],'stimulus':embedding_frame(assets['vectors'][v['text']],mapping,1.).to_dict()}
                    for v in lessons]
            raw_sources.append({'key':key,'seed':seed,'core_seed':CORE_SEED,'condition':condition,
                'lessons':lessons,'frames':frames,'definition_sha256':sha(folder/'definition.json'),
                'readouts':definition['readouts'],'historical_wall_seconds':old['wall_seconds']})
            for end in CHECKPOINTS:
                cp=folder/'checkpoints'/str(end);summary=read(cp/'summary.json')
                assert int(summary['time_us'])==end*1000000 and summary['life']=='active'
                source_checkpoints.append({'source':key,'seconds':end,'state_sha256':summary['state_hash'],
                    'artifact_sha256':sha(cp/'state.tmind'),'context_sha256':sha(cp/'context.json.gz'),
                    'tape_cursor':summary['tape_cursor'],'lesson_cursor':summary['lesson_cursor']})
            for end in PROBES:
                for cue in range(9):
                    case=read(OLD/'cases'/f'{key}-t{end}-p{cue}'/'result.json')
                    rows.append(case)
            for cue in (1,3,5,7):rows.append(read(OLD/'cases'/f'd1-{key}-t830-p{cue}'/'result.json'))
    assert len(raw_sources)==10 and len(source_checkpoints)==90 and len(rows)==490
    assert Counter(v['kind'] for v in rows)=={'probe':450,'probe-dose':40}
    assert all(v['life']=='active' and len(v['windows'])==4 for v in rows)
    for row in rows:
        definition_path=OLD/'cases'/row['key']/'definition.json'
        definition=read(definition_path)
        if 'probe_intensity' in row:assert row['probe_intensity']==definition['probe_intensity']
        row['probe_intensity']=definition['probe_intensity']
        row['definition_sha256']=sha(definition_path)
        cue=row['cue_index'];text=None if cue==8 else NAMES[cue//2]+('是' if cue%2 else '')
        words=WORDS[::-1] if row['condition']=='reversed' else WORDS
        assert row['probe']==text and row['label']==(None if cue==8 else words[cue//2])
        assert row['probe_intensity']==(1. if row['kind']=='probe-dose' else .5)
        assert int(row['time_us'])==(row['checkpoint']+2)*1000000
        assert all(len(v['features'])==256 for v in row['windows'])
    artifacts=('assets.json','head-17.safetensors','head-29.safetensors','physical-telemetry.jsonl',
        'physical-telemetry.complete.json','physical-telemetry.metadata.json')
    return {'created_engines':0,'created_decoders':0,'material_blocks':2,'teaching_individuals':10,
        'core_seed':CORE_SEED,'sources':raw_sources,'checkpoints':source_checkpoints,
        'diagnostics':[{k:v[k] for k in ('key','kind','source','seed','condition','checkpoint','probe','cue_index','label',
            'probe_intensity','definition_sha256','final_state_hash','wall_seconds')} for v in rows],
        'artifacts':{name:{'bytes':(OLD/name).stat().st_size,'sha256':sha(OLD/name)} for name in artifacts},
        'background_records':len(background),'background_channels':len(bg_channels),
        'head_identity_basis':'channel','historical_head_fields':['activation'],
        'historical_head_bins':4,'historical_head_buckets':64}


if __name__=='__main__':
    value=inventory()
    print(json.dumps({'created_engines':0,'created_decoders':0,'material_blocks':value['material_blocks'],
        'teaching_individuals':value['teaching_individuals'],'checkpoints':len(value['checkpoints']),
        'diagnostics':len(value['diagnostics']),'background_records':value['background_records'],
        'core_seed':value['core_seed']},ensure_ascii=False))
