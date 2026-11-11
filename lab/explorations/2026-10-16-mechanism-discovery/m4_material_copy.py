"""Copy only frozen, selected E69 evidence into a separate publication package.

No Core imports, source writes, subject loading or simulated-time advancement.
An existing complete copy is accepted only after its hash and size match.
Interrupted partial files are preserved for inspection, never silently replaced.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_child(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('member escapes evidence root')
    return path


def copy_selected(work):
    manifest_path = work / 'materials.json'
    manifest = json.loads(manifest_path.read_bytes())
    source = Path(manifest['source_root']).resolve()
    destination = work / 'source-evidence'
    assert manifest['identity'] == 'e69-5.1-223'
    assert len(manifest['members']) == 594
    assert (source / 'STOP').is_file()
    assert not (source / 'subject/in-flight.json').exists()
    assert not (source / 'in-flight.json').exists()
    for relative in ('STOP', 'subject/latest.json'):
        assert sha(source / relative) == manifest['members'][relative]['sha256']
    total = sum(v['bytes'] for v in manifest['members'].values())
    # Copy plus a conservative archive and independent API readback budget.
    if shutil.disk_usage(work).free < 25 * 2**30 + total * 3.03 + 64 * 2**20:
        raise RuntimeError('insufficient copy/archive/readback reserve')
    for relative, expected in manifest['members'].items():
        original = safe_child(source, relative)
        target = safe_child(destination, relative)
        if target.exists():
            assert target.stat().st_size == expected['bytes'] and sha(target) == expected['sha256']
            continue
        assert original.stat().st_size == expected['bytes']
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.partial')
        digest = hashlib.sha256()
        size = 0
        with original.open('rb') as src, partial.open('xb') as dst:
            while block := src.read(2 * 2**20):
                dst.write(block)
                digest.update(block)
                size += len(block)
            dst.flush()
            os.fsync(dst.fileno())
        assert size == expected['bytes'] and digest.hexdigest() == expected['sha256']
        # Exclusive publication: no replacement of any existing complete target.
        os.link(partial, target)
        partial.unlink()
    for relative, expected in manifest['members'].items():
        target = safe_child(destination, relative)
        assert target.stat().st_size == expected['bytes'] and sha(target) == expected['sha256']
    for relative in ('STOP', 'subject/latest.json'):
        assert sha(source / relative) == manifest['members'][relative]['sha256']
    receipt = {'schema': 'threemind.selected-source-copy/1', 'members': len(manifest['members']),
               'bytes': total, 'materials_sha256': sha(manifest_path),
               'source_root': str(source), 'destination': str(destination),
               'source_files_modified': 0, 'complete_E69_copied': False,
               'selected_materials_byte_copied_and_rehashed': True}
    receipt_path = work / 'source-copy-v1.json'
    if receipt_path.exists():
        assert json.loads(receipt_path.read_bytes()) == receipt
    else:
        with receipt_path.open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    copy_selected(parser.parse_args().work.resolve())
