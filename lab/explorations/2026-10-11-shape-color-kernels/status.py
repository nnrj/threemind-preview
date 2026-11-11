"""Compact, read-only progress of the existing E67 hosts and saved stages."""
import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
import shutil

import psutil

ROOT = Path(__file__).resolve().parents[3]
ARMS = ('2', '3.1', '4-adaptive', '4-legacy')


def read(path):
    return json.loads(path.read_bytes())


def host(state, script, log, error_log):
    if not state.exists():
        return {'registered_host': False}
    value = read(state)
    try:
        process = psutil.Process(value['pid'])
        alive = process.is_running() and any(Path(p).name == script for p in process.cmdline())
        value.update(alive=alive, cpu_s=round(sum(process.cpu_times()[:2]), 1),
                     rss_bytes=process.memory_info().rss)
        children = []
        for child in process.children(recursive=True):
            try:
                children.append(dict(pid=child.pid, name=child.name(),
                    scripts=[Path(arg).name for arg in child.cmdline() if arg.endswith('.py')],
                    cpu_s=round(sum(child.cpu_times()[:2]), 1), rss_bytes=child.memory_info().rss))
            except psutil.NoSuchProcess:
                continue
        value['children'] = children
    except psutil.NoSuchProcess:
        value['alive'] = False
    rows = []
    if log.exists():
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size-65536))
            for line in stream.read().decode('utf-8', errors='replace').splitlines():
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and ('lesson' in row or 'questions' in row or 'chapter' in row):
                        rows.append(row)
                except ValueError:
                    pass
        value['progress'] = rows[-1] if rows else None
        value['log_updated'] = datetime.fromtimestamp(log.stat().st_mtime).isoformat(timespec='seconds')
    value['stderr_bytes'] = error_log.stat().st_size if error_log.exists() else None
    return value


def status(work):
    result = dict(now=datetime.now().isoformat(timespec='seconds'), free_disk_GiB=shutil.disk_usage(work).free/2**30,
        two=host(work/'pipeline-status.json', 'pipeline.py', ROOT/'.work/e67-pipeline-20261012.stdout.log',
                 ROOT/'.work/e67-pipeline-20261012.stderr.log'),
        four=host(ROOT/'.work/e67-four-pipeline-status.json', 'continue_four.py',
                  ROOT/'.work/e67-four-20261012.stdout.log', ROOT/'.work/e67-four-20261012.stderr.log'), arms={})
    for name, path in (('four_heartbeat', ROOT/'.work/e67-four-heartbeat.json'),
                       ('platform_sync', ROOT/'.work/e67-four-sync-status.json')):
        if path.exists():
            result[name] = read(path)
    for arm in ARMS:
        base = work/'arms'/arm
        row = dict(born=(base/'initial-teaching/birth/complete.json').exists(), scores={})
        for stage in ['development-0', 'development-1', 'development-2', 'development-3', 'final']:
            path = base/stage/'result.json'
            if path.exists():
                value = read(path)
                row['scores'][stage] = {key: value[key] for key in ('correct', 'n', 'shape', 'color', 'pairs')}
        folders = [p for p in base.iterdir() if p.is_dir()] if base.exists() else []
        if folders:
            folder = max(folders, key=lambda p: p.stat().st_mtime_ns)
            row['latest_folder'] = folder.name
            row['stage_complete'] = (folder/'result.json').exists()
            row['saved_trials'] = len(list((folder/'trials').glob('*.json')))
            clips = sorted((folder/'clips').glob('*.json.gz'))
            row['saved_clips'] = len(clips)
            if clips:
                clip = json.loads(gzip.decompress(clips[-1].read_bytes()))
                row['latest_trial'] = {k: v for k, v in clip['trial'].items()
                                       if k in ('lesson', 'question_id', 'start_us', 'end_us')}
        result['arms'][arm] = row
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path('E:/ThreeMindData/experiments/2026-10-11-shape-color-kernels'))
    print(json.dumps(status(parser.parse_args().work.resolve()), ensure_ascii=False))
