import gzip
import json

from lab.tools.ocean_contact import ContactOcean,ContactProtocol
from lab.tools.ocean_encounter import observe_encounter


def test_physically_lost_body_does_not_repeat_last_activity(tmp_path):
    w=ContactOcean(ContactProtocol(founders=2,nutrient_initial=0,reproduction=False,
        maximum_age_us=100000).model_dump(by_alias=True))
    result=observe_encounter(w,tmp_path/'case',{'focal':0,'target':1,'task':'hunt'},'intact',seconds=.5)
    assert not result['physical']
    with gzip.open(tmp_path/'case/activity.json.gz','rt',encoding='utf-8') as stream:activity=json.load(stream)
    times=[row['t'] for row in activity]
    assert times==sorted(set(times)) and max(times)<=.1
