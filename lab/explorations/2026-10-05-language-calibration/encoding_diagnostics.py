"""Read-only post-calibration encoding inspection; never a new selection criterion."""
import json

import numpy as np
import torch
from experiment import HERE, TEST_NAMES, TEST_SEEDS, WORK, Input, protocol, read_json

from lab.tools.service_study import new_json
from threemind_transformer.scratch_language import load


def main():
    torch.set_num_threads(2);rows=[]
    selected=read_json(WORK/'parameter-selection.json')
    for seed in TEST_SEEDS:
        path=WORK/'models'/f'input-{seed}.safetensors'
        if not path.exists():raise RuntimeError('do not train a missing model during inspection')
        p=protocol(seed).model_copy(update={'input_checkpoint_sha256':read_json(path.with_suffix('.json'))['checkpoint_sha256']})
        inp=Input(selected['route'],seed,load(p,'input','cpu',path)[1])
        tokens=(*TEST_NAMES,'是','。')
        vectors=[dict(inp.frames(t)[0]['stimulus'].channels) for t in tokens]
        channels=sorted({c for v in vectors for c in v})
        matrix=np.array([[v.get(c,0) for c in channels] for v in vectors])
        normalized=matrix/np.maximum(1e-12,np.linalg.norm(matrix,axis=1))[:,None]
        overlap=[[len(set(a)&set(b)) for b in vectors] for a in vectors]
        rows.append({'seed':seed,'tokens':tokens,'nonzero_channel_overlap':overlap,
                     'cosine_similarity':(normalized@normalized.T).tolist(),
                     'distinct_token_vectors':len({tuple(sorted(v.items())) for v in vectors}),
                     'channels':[sorted(v) for v in vectors],
                     'scope':'isolated token prefixes; contextual later-character encodings may differ'})
    new_json(HERE/'encoding-diagnostics.json',{'posthoc_readonly':True,'used_for_selection':False,'rows':rows})
    print(json.dumps(rows,ensure_ascii=False))


if __name__=='__main__':main()
