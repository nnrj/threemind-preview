import json
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_pilot as p


def test_archives_detect_tampering_missing_and_duplicate_members():
    folder = p.ROOT/'.work/mechanism-preparation-20261016'/('archive-test-'+uuid4().hex)
    folder.mkdir(parents=True)
    source = folder/'whole.json'
    source.write_text('{"simulated":true}', encoding='utf-8')
    manifest = {'members': [{'path': source.name, 'sha256': p.sha(source), 'bytes': source.stat().st_size}]}
    target = folder/'valid.zip'
    with zipfile.ZipFile(target, 'x') as z:
        z.write(source, source.name)
        z.writestr('originals-manifest-v1.json', json.dumps(manifest))
    p.verify_archive(target, manifest)
    broken = folder/'broken.zip'
    with zipfile.ZipFile(broken, 'x') as z:
        z.writestr(source.name, '{"simulated":false}')
        z.writestr('originals-manifest-v1.json', json.dumps(manifest))
    with pytest.raises(ValueError, match='member mismatch'):
        p.verify_archive(broken, manifest)
    wrong = folder/'missing.zip'
    with zipfile.ZipFile(wrong, 'x') as z:
        z.writestr('originals-manifest-v1.json', json.dumps(manifest))
    with pytest.raises(ValueError, match='membership mismatch'):
        p.verify_archive(wrong, manifest)


def test_raw_inventory_excludes_only_publication_control_and_readback():
    folder = p.ROOT/'.work/mechanism-preparation-20261016'/('inventory-test-'+uuid4().hex)
    for name in ['cases/whole.json', 'postprocessing/report.zh.md', '.research-records/pending/x.json',
                 'readback/originals-v1.zip', 'publication/verification.json', 'worker.lock']:
        target = folder/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('synthetic fixture', encoding='utf-8')
    assert [x.relative_to(folder).as_posix() for x in p.file_set(folder)] == ['cases/whole.json', 'postprocessing/report.zh.md']
