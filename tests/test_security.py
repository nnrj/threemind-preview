from pathlib import Path
import uuid
import shutil
import json
from dataclasses import asdict

from cryptography.fernet import Fernet

from threemind.ai import Provider
from threemind.security import SecretStore


def test_provider_store_encrypts_credentials():
    tmp_path = Path(f".security-test-{uuid.uuid4().hex}")
    store = SecretStore(tmp_path)
    provider = Provider(id="x", name="X", base_url="https://example.test", model="", api_key="super-secret")
    store.save([asdict(provider)])
    assert b"super-secret" not in (tmp_path / "ai-providers.enc").read_bytes()
    assert store.load()[0]["api_key"] == "super-secret"
    shutil.rmtree(tmp_path)


def test_provider_store_copies_the_pre_rename_key_without_reencrypting_data():
    tmp_path = Path(f".security-test-{uuid.uuid4().hex}")
    tmp_path.mkdir()
    key = Fernet.generate_key()
    (tmp_path / ".bluebox.key").write_bytes(key)
    payload = [{"id": "legacy", "api_key": "still-readable"}]
    (tmp_path / "ai-providers.enc").write_bytes(Fernet(key).encrypt(json.dumps(payload).encode()))

    store = SecretStore(tmp_path)

    assert store.load() == payload
    assert (tmp_path / ".threemind.key").read_bytes() == key
    assert (tmp_path / ".bluebox.key").read_bytes() == key
    shutil.rmtree(tmp_path)
