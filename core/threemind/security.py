from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class SecretStore:
    """Small local encrypted store for provider credentials.

    The key is kept separately from the ciphertext and may be supplied through
    THREEMIND_SECRET for deployments that use an external secret manager.
    """

    def __init__(self, directory: Path, *, data_name: str = "ai-providers.enc"):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.key_path = self.directory / ".threemind.key"
        self.data_path = self.directory / data_name
        self._fernet = Fernet(self._load_key())

    def _load_key(self) -> bytes:
        configured = os.getenv("THREEMIND_SECRET")
        if configured:
            return configured.encode()
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        legacy_key_path = self.directory / ".bluebox.key"
        if legacy_key_path.exists():
            # Copy rather than move: a failed or interrupted product upgrade
            # must not make the existing encrypted provider store unrecoverable.
            key = legacy_key_path.read_bytes().strip()
            temporary = self.key_path.with_suffix(".tmp")
            temporary.write_bytes(key)
            os.replace(temporary, self.key_path)
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass
            return key
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            self.key_path.chmod(0o600)
        except OSError:
            pass
        return key

    def load(self) -> list[dict[str, Any]]:
        if not self.data_path.exists():
            return []
        try:
            payload = self._fernet.decrypt(self.data_path.read_bytes())
            value = json.loads(payload.decode("utf-8"))
            return value if isinstance(value, list) else []
        except (InvalidToken, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("unable to decrypt provider store") from exc

    def save(self, items: list[dict[str, Any]]) -> None:
        payload = json.dumps(items, ensure_ascii=False).encode("utf-8")
        tmp = self.data_path.with_suffix(".tmp")
        tmp.write_bytes(self._fernet.encrypt(payload))
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        os.replace(tmp, self.data_path)
