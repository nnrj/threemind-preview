"""Lossless typed data and independent integrity rejection; no simulation."""
import json,lzma
import pytest
import m4_compact_evidence_v2 as c


@pytest.mark.parametrize('value',[{},[],[{},{}],['C',3,[],[]],
    [{'a':1,'b':[1,2]},{'a':2,'b':[]}],{'x':True,'n':None,'s':'汉字','v':-0.0,'large':2**63},
    {0:[{'x':'1','y':1.1},{'x':1,'y':None}],'one':[{'a':1},{'b':2}]}])
def test_exact_json_roundtrip(value):
    assert c.canonical(c.decode(c.encode(value)))==c.canonical(value)


def test_integrity_rejects_tampering():
    body=c.encode([{'x':1},{'x':2}]);v=json.loads(lzma.decompress(body))
    v['canonical_sha256']='0'*64
    with pytest.raises(ValueError,match='content differs'):c.decode(lzma.compress(json.dumps(v).encode()))
    with pytest.raises(ValueError,match='column length'):c.unpack(['C',2,['x'],[['L',[1]]]])


@pytest.mark.parametrize('value',[(3,(1,2,3),None),('C',2,[],[]),{'rng':(3,(1,2,3),None),'edges':[(1,2),(2,3)]}])
def test_native_tuples_are_explicitly_tagged(value):
    assert c.canonical(c.decode(c.encode(value)))==c.canonical(value)
