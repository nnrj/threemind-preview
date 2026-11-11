"""Small authenticated secrets, with the deployment key kept outside PostgreSQL."""

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from .config import ROOT


class SecretBox:
    def __init__(self, keys: tuple[str, ...]):
        self.box = MultiFernet([Fernet(key.encode()) for key in keys]) if keys else None

    def seal(self, value: dict) -> str:
        if self.box is None:
            raise ValueError("尚未配置供应商密钥加密钥；工作站请用 workstation 启动，服务器配置 THREEMIND_SECRET_KEYS")
        return self.box.encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()

    def open(self, value: str) -> dict:
        if self.box is None:
            raise ValueError("供应商密钥加密钥未配置")
        try:
            return json.loads(self.box.decrypt(value.encode()))
        except InvalidToken:
            raise ValueError("无法解密供应商凭据；请恢复对应部署密钥，或重新填写供应商凭据") from None


def ensure_local_key(path: Path = ROOT / ".env"):
    """Only called by the workstation launcher / explicit deployment setup."""
    if os.getenv("THREEMIND_SECRET_KEYS"):
        return
    # Existing blank entries must be replaced; dotenv uses the first occurrence.
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    present = [line.split("=", 1)[1].strip() for line in lines if line.startswith("THREEMIND_SECRET_KEYS=")]
    key = next((value for value in present if value), None) or Fernet.generate_key().decode()
    if not any(present):
        lines = [line for line in lines if not line.startswith("THREEMIND_SECRET_KEYS=")]
        lines.append("THREEMIND_SECRET_KEYS=" + key)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    os.environ["THREEMIND_SECRET_KEYS"] = key
