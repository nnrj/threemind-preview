"""Measure saved E67 subjects and research overhead without advancing them."""
from __future__ import annotations

import argparse
import ctypes
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ARMS = ('2', '3.1', '4-adaptive', '4-legacy')
ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024**2):
            h.update(chunk)
    return h.hexdigest()


def files(folder):
    result = []
    for path in Path(folder).rglob('*'):
        if path.is_symlink():
            raise ValueError('do not attribute linked external data: ' + str(path))
        if path.is_file():
            result.append(path)
    return sorted(result)


def allocated(path):
    """File allocation reported by Windows, including cluster rounding."""
    if os.name != 'nt':
        return None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    class StandardInfo(ctypes.Structure):
        _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                    ('links', ctypes.c_ulong), ('delete_pending', ctypes.c_ubyte),
                    ('directory', ctypes.c_ubyte)]
    create = kernel.CreateFileW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                       ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
    create.restype = ctypes.c_void_p
    info = kernel.GetFileInformationByHandleEx
    info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    info.restype = ctypes.c_int
    close = kernel.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    handle = create(str(Path(path).resolve()), 0, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        value = StandardInfo()
        if not info(handle, 1, ctypes.byref(value), ctypes.sizeof(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.allocation
    finally:
        close(handle)


def size(paths):
    paths = list(paths)
    values = [allocated(p) for p in paths]
    return dict(files=len(paths), bytes=sum(p.stat().st_size for p in paths),
                allocated_bytes=sum(values) if all(v is not None for v in values) else None)


def memory_probe(source):
    """Isolated CPU restoration: no teacher, recorder, input or simulation."""
    sys.path.insert(0, str(ROOT))
    os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '2'
    import psutil
    import torch
    from lab.tools.recognition_session import RecognitionSystem

    torch.set_num_threads(2)
    before = {p.relative_to(source).as_posix(): digest(p) for p in files(source)}
    gc.collect()
    process = psutil.Process()
    baseline = process.memory_info().rss
    individual = RecognitionSystem.restore(source, device='cpu')
    gc.collect()
    restored = process.memory_info().rss
    after = {p.relative_to(source).as_posix(): digest(p) for p in files(source)}
    if before != after:
        raise ValueError('read-only restoration modified original files')
    return dict(baseline_rss=baseline, restored_rss=restored,
                restoration_rss_delta=restored-baseline,
                identity=individual.identity, kernel=individual.session.engine.dynamics,
                time_us=individual.session.engine.time_us, core_advanced=False,
                device='cpu', originals_unchanged=True,
                interpretation='Process RSS increase after one complete restoration; includes allocator/native runtime effects, not an exact per-object heap size or GPU measurement.')


def measure(work, arms, stage='fit-3', resident=True):
    result = dict(schema='threemind.e67-storage/1', measured_at=datetime.now(timezone.utc).isoformat(),
                  checkpoint_stage=stage, core_advanced=False, arms={})
    attributed = set()
    for arm in arms:
        base = work/'arms'/arm
        source = base/stage/'system'
        if not (source/'complete.json').exists():
            raise ValueError('complete subject required: ' + str(source))
        originals, replay = files(base), files(work/'replays'/arm)
        if set(originals) & set(replay):
            raise ValueError('overlapping file categories')
        attributed.update(originals + replay)
        pure = files(source)
        with gzip.open(source/'system.json.gz', 'rb') as stream:
            system_bytes = stream.read()
        system = json.loads(system_bytes)
        core = system['session']['core']
        core_bytes = json.dumps(core, ensure_ascii=False, sort_keys=True,
                                separators=(',', ':'), allow_nan=False).encode('utf-8')
        all_size, pure_size = size(originals+replay), size(pure)
        row = dict(originals=size(originals), replays=size(replay), all_files=all_size,
                   complete_individual=pure_size,
                   research_extra_bytes=all_size['bytes']-pure_size['bytes'],
                   checkpoint=source.relative_to(work).as_posix(),
                   checkpoint_manifest={p.relative_to(source).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p)) for p in pure},
                   identity=system['identity'], core_nodes=len(core['nodes']), core_edges=len(core['edges']),
                   core_canonical_json_bytes=len(core_bytes),
                   core_standalone_gzip_bytes=len(gzip.compress(core_bytes, compresslevel=9, mtime=0)),
                   system_json_uncompressed_bytes=len(system_bytes))
        if resident:
            run = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                                  'memory-probe', '--source', str(source)],
                                 cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8')
            row['isolated_restoration_memory'] = json.loads(run.stdout)
            if row['isolated_restoration_memory']['identity'] != row['identity']:
                raise ValueError('restoration measured a different individual')
        result['arms'][arm] = row
    all_paths = files(work)
    shared = [p for p in all_paths if p not in attributed]
    result.update(study_files=size(all_paths), shared_or_other_files=size(shared),
                  free_disk_bytes=shutil.disk_usage(work).free,
                  definitions=dict(
                      complete_individual='Exactly one current complete checkpoint: Core, personal peripheral weights/optimizer/RNG, world/body, mappings and required recent readout state. No older checkpoints, trajectories, questions, feature corpora, videos or report exports.',
                      all_files='All files in each arm directory plus its replay directory, including repeated checkpoints and interrupted originals. Shared protocols, recorder journal and other study files are listed once separately.',
                      core_only='Derived canonical JSON and independently gzip-encoded size, calculated without writing another copy. This is not a complete individual and cannot be subtracted from a jointly compressed file to infer exact component allocation.',
                      exclusions='Shared installed application/dependencies and PostgreSQL data/index pages are not assigned to individual models. Database metadata is not zero; these totals explicitly measure managed research files. Directory/MFT overhead and hardlink physical deduplication are not attributed.'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('measure', 'memory-probe'))
    parser.add_argument('--work', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    parser.add_argument('--stage', default='fit-3')
    parser.add_argument('--skip-memory', action='store_true')
    args = parser.parse_args()
    if args.mode == 'memory-probe':
        if args.source is None:
            parser.error('--source is required')
        print(json.dumps(memory_probe(args.source.resolve()), ensure_ascii=False))
        return
    if args.work is None or args.output is None:
        parser.error('--work and --output are required')
    if args.output.exists():
        raise ValueError('preserve the existing measurement edition')
    result = measure(args.work.resolve(), args.arms, args.stage, not args.skip_memory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'output': str(args.output), 'arms': args.arms, 'study_files': result['study_files']}))


if __name__ == '__main__':
    main()
