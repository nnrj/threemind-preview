"""A half-written observation must never be reported as a complete world frame."""
import gzip
import json
from lab.tools.ocean_live_status import Tail


def test_partial_compressed_line_is_not_published(tmp_path):
    path=tmp_path/'trajectory.jsonl.gz';tail=Tail(path)
    frame=lambda t:json.dumps({'time_us':t,'groups':{'A':{'physical':3}},'nutrient_count':12}).encode()
    with gzip.open(path,'wb') as writer:
        writer.write(frame(100));writer.flush();tail.update()
        assert tail.latest is None
        writer.write(b'\n'+frame(200)+b'\n'+frame(300)[:15]);writer.flush();tail.update()
        assert tail.latest['time_us']==200
        writer.write(frame(300)[15:]+b'\n');writer.flush();tail.update()
        assert tail.latest['time_us']==300
    tail.update()
    assert tail.decoder.eof and tail.latest['groups']['A']['physical']==3
