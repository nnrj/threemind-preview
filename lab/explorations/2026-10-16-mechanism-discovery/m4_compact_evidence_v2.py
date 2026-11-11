"""V2: tag native tuple sequences explicitly; preserves frozen failed v1."""
"""Lossless typed JSON column packing; new evidence only, no simulation calls."""
import hashlib,json,lzma,os
from pathlib import Path

SCHEMA='threemind.lossless-columnar-json/2'


def canonical(value):
    def normalize(v):
        if isinstance(v,(list,tuple)):
            items=[normalize(x) for x in v]
            return v if isinstance(v,list) and all(a is b for a,b in zip(v,items)) else items
        if isinstance(v,dict):
            if any(type(k) not in (str,int) for k in v):raise ValueError('JSON object key type')
            if len({str(k) for k in v})!=len(v):raise ValueError('colliding JSON object keys')
            items={str(k):normalize(x) for k,x in v.items()}
            return v if all(type(k) is str for k in v) and all(v[k] is x for k,x in items.items()) else items
        return v
    return json.dumps(normalize(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def pack(value):
    if isinstance(value,(list,tuple)):
        if value and all(isinstance(x,dict) and tuple(x)==tuple(value[0]) for x in value):
            keys=list(value[0])
            return ['C',len(value),[str(k) for k in keys],[pack([x[k] for x in value]) for k in keys]]
        return ['L',[pack(x) for x in value]]
    if isinstance(value,dict):
        # JSON object keys are strings. State and trajectory payloads use them;
        # derived maps may have integer keys, canonical JSON normalizes those.
        return ['D',[str(k) for k in value],[pack(x) for x in value.values()]]
    return value


def unpack(value):
    if not isinstance(value,list):return value
    tag=value[0]
    if tag=='L':return [unpack(x) for x in value[1]]
    if tag=='D':
        if len(value[1])!=len(value[2]) or len(set(value[1]))!=len(value[1]):raise ValueError('object columns')
        return dict(zip(value[1],[unpack(x) for x in value[2]]))
    if tag=='C':
        n,keys,columns=value[1],value[2],[unpack(x) for x in value[3]]
        if type(n) is not int or n<0 or len(keys)!=len(columns) or len(set(keys))!=len(keys):raise ValueError('column table')
        if any(not isinstance(c,list) or len(c)!=n for c in columns):raise ValueError('column length')
        return [dict(zip(keys,row)) for row in zip(*columns)] if keys else [{} for _ in range(n)]
    raise ValueError('unknown packing tag')


def encode(value):
    # Avoid retaining a second full decoded copy of a large physical state.
    raw=canonical(value);sha=hashlib.sha256(raw).hexdigest();del raw
    envelope={'schema':SCHEMA,'canonical_sha256':sha,'value':pack(value)}
    return lzma.compress(json.dumps(envelope,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode(),preset=3)


def decode(body):
    envelope=json.loads(lzma.decompress(body))
    if envelope['schema']!=SCHEMA:raise ValueError('evidence schema')
    value=unpack(envelope['value'])
    if hashlib.sha256(canonical(value)).hexdigest()!=envelope['canonical_sha256']:raise ValueError('decoded content differs')
    return value


def read(path):return decode(Path(path).read_bytes())


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=encode(value)
    if path.exists():raise FileExistsError(path)
    part=path.with_name(path.name+'.partial')
    with part.open('xb') as out:out.write(body);out.flush();os.fsync(out.fileno())
    os.link(part,path);part.unlink()
    return {'sha256':hashlib.sha256(body).hexdigest(),'byte_count':len(body)}
