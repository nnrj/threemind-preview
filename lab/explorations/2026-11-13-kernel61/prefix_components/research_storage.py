"""Complete, checksummed research state; intentionally outside production import."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from threemind_core import StateImage
from threemind_core.engine import canonical_bytes
from research_kernel import KERNEL_ID, STATE_SCHEMA, ResearchConfig, definition

class Codec:
    @staticmethod
    def encode(image):
        value=image.to_dict()
        assert value['dynamics']==KERNEL_ID and value['schema']==STATE_SCHEMA
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        manifest={'format':'r51t6/research-state/1','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'state_hash':image.digest}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
            z.writestr('state.json',raw);z.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
        return out.getvalue()

    @staticmethod
    def decode(raw):
        assert len(raw)<64*2**20
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            assert sorted(z.namelist())==['manifest.json','state.json']
            assert sum(x.file_size for x in z.infolist())<64*2**20
            data=z.read('state.json');m=json.loads(z.read('manifest.json'))
        assert m['format']=='r51t6/research-state/1'
        assert len(data)==m['bytes'] and hashlib.sha256(data).hexdigest()==m['sha256']
        value=json.loads(data);image=StateImage.from_dict(value)
        assert image.digest==m['state_hash'] and value['dynamics']==KERNEL_ID and value['schema']==STATE_SCHEMA
        expected=definition(ResearchConfig(**value['config']))
        assert value['definition']==expected
        assert value['definition_hash']==hashlib.sha256(canonical_bytes(expected)).hexdigest()
        return image

def save(path,image):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=Codec.encode(image);assert Codec.decode(raw).digest==image.digest
    with path.open('xb') as f:f.write(raw)

def image(path):return Codec.decode(Path(path).read_bytes())
