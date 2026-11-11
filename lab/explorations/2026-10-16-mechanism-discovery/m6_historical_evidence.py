"""Immutable streaming evidence for the registered historical M6 factorial.

No engine is constructed here. Paths, time order and raw hashes fail closed.
An interrupted writer retains its partial original for an explicit review.
"""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import pilot_m2 as m

START_US = 20_000_000
PERIOD_US = 20_000
END_US = 30_000_000
MODES = ('live', 'muted')
OPERATIONS = ('sham', 'target', 'matched', 'restored')


def cases():
    return [{'world': world, 'mode': mode, 'operation': operation,
             'id': f'w{world}-{mode}-{operation}'}
            for world in range(2) for mode in MODES for operation in OPERATIONS]


def checked_case(value):
    if value not in cases():
        raise ValueError('case differs from the complete frozen factorial')
    return dict(value)


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('evidence path escapes its root')
    return path


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_row(row, expected_us):
    if row['action_time_us'] != expected_us or row['time_us'] != expected_us + PERIOD_US:
        raise ValueError('missing, duplicated or unordered physical frame')
    if row['native']['time_us'] != row['time_us']:
        raise ValueError('native frame time differs')
    for body, action in row['actions'].items():
        if not isinstance(body, str) or str(int(body)) != body or int(body) < 0:
            raise ValueError('noncanonical body identity')
        if len(action) != 3 or any(not math.isfinite(v) or abs(v) > 1 + 1e-12 for v in action):
            raise ValueError('nonfinite or out-of-range physical action')
    # The actually applied pre-physics action remains evidence even if the
    # body dies before the native sensory callback in this very step.
    m.encoded(row)


class Trajectory:
    def __init__(self, path, start_us):
        self.path = Path(path)
        self.partial = self.path.with_suffix(self.path.suffix + '.partial')
        if self.path.exists() or self.partial.exists():
            raise FileExistsError('trajectory was already attempted')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = self.partial.open('xb')
        self.stream = gzip.GzipFile(filename='', fileobj=self.raw, mode='wb', mtime=0)
        self.sha = hashlib.sha256()
        self.start_us = self.current_us = start_us
        self.count = 0
        self.closed = False

    def append(self, row):
        validate_row(row, self.current_us)
        raw = m.encoded(row) + b'\n'
        self.stream.write(raw)
        self.sha.update(raw)
        self.current_us += PERIOD_US
        self.count += 1

    def abort(self):
        if not self.closed:
            self.stream.close()
            self.raw.close()
            self.closed = True

    def finish(self):
        if self.closed:
            raise ValueError('closed trajectory')
        self.stream.close()
        self.raw.flush()
        os.fsync(self.raw.fileno())
        self.raw.close()
        self.closed = True
        os.link(self.partial, self.path)
        self.partial.unlink()
        return {'start_us': self.start_us, 'end_us': self.current_us,
                'frames': self.count, 'raw_sha256': self.sha.hexdigest(),
                'sha256': file_sha(self.path), 'bytes': self.path.stat().st_size}


def read_segment(path, receipt):
    path = Path(path)
    if path.stat().st_size != receipt['bytes'] or file_sha(path) != receipt['sha256']:
        raise ValueError('trajectory original changed')
    current = receipt['start_us']
    sha = hashlib.sha256()
    count = 0
    with gzip.open(path, 'rb') as stream:
        for raw in stream:
            if not raw.endswith(b'\n'):
                raise ValueError('truncated trajectory line')
            row = json.loads(raw)
            if m.encoded(row) + b'\n' != raw:
                raise ValueError('trajectory is not canonical')
            validate_row(row, current)
            current += PERIOD_US
            count += 1
            sha.update(raw)
            yield row
    if (current, count, sha.hexdigest()) != (receipt['end_us'], receipt['frames'], receipt['raw_sha256']):
        raise ValueError('trajectory receipt differs')


def verify_chain(folder, segments, start_us, end_us):
    """All frames are consumed even when a caller only needs the first second."""
    current = start_us
    digest = hashlib.sha256()
    primary = []
    count = 0
    for segment in segments:
        if segment['start_us'] != current or segment['end_us'] <= current:
            raise ValueError('noncontiguous or empty trajectory segment')
        for row in read_segment(inside(folder, segment['path']), segment):
            digest.update(m.encoded(row) + b'\n')
            count += 1
            if row['action_time_us'] < START_US + 1_000_000:
                primary.append(row)
        current = segment['end_us']
    if current != end_us or count != (end_us - start_us) // PERIOD_US:
        raise ValueError('trajectory chain does not reach its declared boundary')
    return {'raw_sha256': digest.hexdigest(), 'frames': count, 'primary': primary}
