"""Read-only independent arithmetic and artifact audit of R51c."""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))
import support as s
from threemind_runtime import ArtifactCodec


def disk_allocation(path):
    """FileStandardInfo allocation, distinct from uncompressed file length."""
    class Standard(ctypes.Structure):
        _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                    ('links', ctypes.c_ulong), ('delete_pending', ctypes.c_ubyte),
                    ('directory', ctypes.c_ubyte)]
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                             ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)
    k.CreateFileW.restype = ctypes.c_void_p
    k.GetFileInformationByHandleEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)
    k.CloseHandle.argtypes = (ctypes.c_void_p,)
    h = k.CreateFileW(str(path), 0, 7, None, 3, 0, None)
    if h == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Standard()
        if not k.GetFileInformationByHandleEx(h, 1, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'allocated_bytes': info.allocation, 'logical_bytes': info.end, 'hard_links': info.links}
    finally:
        k.CloseHandle(h)


def compatible(doc):
    doc = copy.deepcopy(doc)
    for k in ('schema', 'dynamics', 'definition', 'definition_hash'):
        doc.pop(k, None)
    for k in ('deletion_strategy', 'activation_send_threshold', 'inhibition_send_threshold'):
        doc['config'].pop(k, None)
    return doc


def audit(work):
    assert not (work / 'in-flight.json').exists()
    assert not (work / 'STOP').exists()
    frozen = json.loads((work / 'frozen.json').read_bytes())
    for p, digest in frozen['sources'].items():
        assert s.sha(ROOT / p) == digest, p
    assert s.sha(frozen['module_path']) == frozen['module_sha256']
    assert s.sha(HERE / 'protocol.md') == frozen['protocol_sha256']
    assert s.sha(HERE / 'benchmark.py') == frozen['runner_sha256']
    rows = json.loads((work / 'results.json').read_bytes())
    reported = json.loads((work / 'summary.json').read_bytes())
    assert len(rows) == len({r['key'] for r in rows}) == 48
    docs = {}
    allocation = {}
    for r in rows:
        folder = work / 'trials' / r['key']
        assert json.loads((folder / 'result.json').read_bytes()) == r
        for stage in ('initial', 'final'):
            image = ArtifactCodec.decode((folder / (stage + '.tmind')).read_bytes())
            assert image.digest == r[stage]
            if stage == 'final':
                assert s.sha(folder / 'final.tmind') == r['file']['sha256']
                docs[r['key']] = image.to_dict()
                allocation[r['key']] = disk_allocation(folder / 'final.tmind')
    comparisons = []
    for n, repeats in ((1024, 5), (4096, 3)):
        for i in range(repeats):
            assert compatible(docs[f'{n}-{i}-60']) == compatible(docs[f'{n}-{i}-61-global-zero'])
        by_label = {}
        for label in sorted({r['label'] for r in rows}):
            rs = [r for r in rows if r['nodes'] == n and r['label'] == label]
            assert len(rs) == repeats
            assert len({r['final'] for r in rs}) == 1
            elapsed = statistics.median(r['wall_s'] for r in rs)
            published = next(g for g in reported['groups'] if g['nodes'] == n and g['label'] == label)
            assert elapsed == published['wall_s']
            by_label[label] = {'median_wall_s': elapsed, **allocation[rs[0]['key']]}
            if label == '61-local':
                assert all(r['audit']['scan_visits'] == 0 and r['timers'] == n for r in rs)
        ratio = by_label['61-local']['median_wall_s'] / by_label['51']['median_wall_s']
        disk_ratio = by_label['61-local']['allocated_bytes'] / by_label['51']['allocated_bytes']
        assert ratio == reported['ratio_to_51'][str(n)] and ratio < 2 and disk_ratio < 2
        comparisons.append({'nodes': n, 'groups': by_label, 'ratio_to_51': ratio,
                            'ratio_to_60': by_label['61-local']['median_wall_s'] / by_label['60']['median_wall_s'],
                            'allocated_ratio_to_51': disk_ratio})
    result = {'passed': True, 'complete_trials': 48, 'decoded_complete_states': 96,
              'exact_60_equivalence_pairs': 8, 'comparisons': comparisons,
              'storage_correction': 'Benchmark GetCompressedFileSizeW values are lengths for these uncompressed files; actual allocation is FileStandardInfo here.'}
    s.base.original(work / 'audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    audit(p.parse_args().work.resolve())
