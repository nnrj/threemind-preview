"""Engineering witnesses for the logical evidence budget, never a subject."""
from pathlib import Path
import os
import stat
from types import SimpleNamespace
import pytest
import evidence_size as e


def test_nested_hidden_zero_and_hardlinked_files(tmp_path):
    (tmp_path/'empty').mkdir()
    (tmp_path/'.hidden').mkdir()
    (tmp_path/'a').write_bytes(b'abc')
    (tmp_path/'.hidden'/'b').write_bytes(b'12345')
    (tmp_path/'zero').write_bytes(b'')
    os.link(tmp_path/'a',tmp_path/'hardlink')
    expected=sum(p.stat().st_size for p in tmp_path.rglob('*') if p.is_file())
    assert expected==11
    assert e.logical_bytes(tmp_path)==dict(logical_bytes=11,files=4)


def test_missing_directory_is_not_an_empty_budget(tmp_path):
    with pytest.raises(FileNotFoundError):e.logical_bytes(tmp_path/'absent')


def test_permission_error_is_not_skipped(monkeypatch):
    def denied(_):raise PermissionError('test')
    monkeypatch.setattr(e.os,'scandir',denied)
    with pytest.raises(PermissionError):e.logical_bytes('irrelevant')


def test_reparse_point_is_rejected(monkeypatch):
    class Entries:
        def __enter__(self):return iter([SimpleNamespace(path='test-link',stat=lambda **kw:SimpleNamespace(
            st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,st_mode=stat.S_IFREG,st_size=900))])
        def __exit__(self,*_):pass
    monkeypatch.setattr(e.os,'scandir',lambda _:Entries())
    with pytest.raises(ValueError,match='reparse point'):e.logical_bytes('irrelevant')


def test_empty_directory(tmp_path):
    assert e.logical_bytes(tmp_path)==dict(logical_bytes=0,files=0)
