import io
import json
import zipfile

import pytest

from lab.tools.ocean_contact_cli import save
from lab.tools.ocean_enclosure import EnclosureOcean
from lab.tools.ocean_species import save_candidate, seed_founders
from threemind_lab import species_library as lib
from threemind_lab.database import LOCAL_USER, NotFound


def candidate(tmp_path):
    w=EnclosureOcean({'schema':'threemind.ocean-enclosure/1','founders':2,'population_limit':3,
                      'nutrient_initial':3,'nutrient_capacity':10})
    w.configure({0:'all',1:'all'},{'all':'core'})
    w.step();save(w,tmp_path/'source')
    save_candidate(tmp_path/'source',0,tmp_path/'candidate.tmspecies',name='测试候选',evidence=[])
    return (tmp_path/'candidate.tmspecies').read_bytes(),w


def test_bundle_preserves_identity_and_reuses_body_mapping_and_structure(tmp_path):
    raw,old=candidate(tmp_path);m,image=lib.inspect_bundle(raw)
    before=old.engines[0].capture_state().digest
    assert image.digest==before and m['traits']['radius']==old.bodies[0].radius
    new=EnclosureOcean(old.p.model_dump(by_alias=True));pos=list(new.bodies[1].position)
    old_nodes=len(image.to_dict()['nodes'])
    seed_founders(new,raw,[1])
    state=new.engines[1].capture_state().to_dict()
    assert old.engines[0].capture_state().digest==before
    assert new.bodies[1].position==pos and new.bodies[1].radius==old.bodies[0].radius
    assert new.seeds[1]==old.seeds[0] and int(state['time_us'])==0
    assert len(state['nodes'])==old_nodes
    assert all(n['activation']==0 for n in state['nodes'])
    assert new.engines[1].metrics()['energy']['reserve']==new.p.initial_energy
    new.step()


def test_bundle_rejects_extra_files_and_wrong_state_identity(tmp_path):
    raw,_=candidate(tmp_path)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        m=json.loads(z.read('manifest.json'));brain=z.read('consciousness.tmind')
    for extra,wrong in ((True,False),(False,True)):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            m['state_hash']='0'*64 if wrong else m['state_hash']
            z.writestr('manifest.json',json.dumps(m));z.writestr('consciousness.tmind',brain)
            if extra:z.writestr('../escape','no')
        with pytest.raises(ValueError):lib.inspect_bundle(buf.getvalue())


def test_library_project_scope_and_roundtrip(database,tmp_path):
    from test_api import client_for
    raw,_=candidate(tmp_path)
    with client_for(database) as client:
        p=client.post('/api/v2/projects',json={'name':'Species A'}).json()['id']
        other=client.post('/api/v2/projects',json={'name':'Species B'}).json()['id']
        base=f'/api/v2/projects/{p}/species'
        row=client.post(base,files={'file':('a.tmspecies',raw,'application/zip')})
        assert row.status_code==201,row.text
        identity=row.json()['id']
        assert len(client.get(base).json())==1
        assert client.post(base,files={'file':('a.tmspecies',raw)}).json()['id']==identity
        assert client.get(f'{base}/{identity}/download').content==raw
        assert client.get(f'/api/v2/projects/{other}/species').json()==[]
        assert client.get(f'/api/v2/projects/{other}/species/{identity}/download').status_code==404
