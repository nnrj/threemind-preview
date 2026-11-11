from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_mechanism as p


def test_two_copy_disk_budget_prevents_archive_before_evidence_write(monkeypatch):
    root = p.ROOT/'.work'/('mechanism-publish-test-'+uuid4().hex)
    root.mkdir(parents=True)
    (root/'fixture.txt').write_text('synthetic evidence', encoding='utf-8')
    class Recorder:
        def save_original(self, name, content):
            with (root/name).open('xb') as f: f.write(content)
    monkeypatch.setattr(p.shutil, 'disk_usage', lambda _: SimpleNamespace(free=25*2**30))
    with pytest.raises(RuntimeError, match='insufficient space'):
        p.archive(root, Recorder())
    assert not (root/'originals-manifest-v1.json').exists()
    monkeypatch.setattr(p.shutil, 'disk_usage', lambda _: SimpleNamespace(free=26*2**30))
    manifest, archive = p.archive(root, Recorder())
    p.verify_archive(archive, manifest)
    assert manifest['members'][0]['path'] == 'fixture.txt'
