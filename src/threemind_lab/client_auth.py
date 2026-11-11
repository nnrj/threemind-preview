"""Host-owned API credentials, separate from scientific state and browser cookies.

Windows encrypts credentials with current-user DPAPI. POSIX hosts use a private
directory and owner-only files. Importing this module creates no files.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .storage_files import checked_path, file_lock

SCHEMA = "threemind.client-auth/1"
SOURCES = ("human", "ai", "script")


class AuthenticationRequired(ValueError):
    pass


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Use an HTTP(S) service origin without credentials, path, query or fragment")
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Remote ThreeMind operation access requires HTTPS")
    return value.rstrip("/")


def _dpapi(raw, *, decrypt=False):
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise AuthenticationRequired("Cannot open protected credentials for this operating-system user")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(target.data)


def expiry_seconds(value):
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            raise ValueError("timezone required")
        return (timestamp - datetime.now(UTC)).total_seconds()
    except (TypeError, ValueError) as error:
        raise AuthenticationRequired("Invalid stored session expiry; run threemind auth login") from error


class CredentialStore:
    def __init__(self, url, *, directory=None, profile="default"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", profile):
            raise ValueError("credential profile must contain 1–64 letters, digits, '_' or '-'")
        self.origin, self.profile = origin(url), profile
        default = (Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local")) / "ThreeMind/auth"
                   if os.name == "nt" else Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state")) / "threemind/auth")
        self.directory = checked_path(Path(directory or os.getenv("THREEMIND_AUTH_DIR") or default).absolute())
        key = hashlib.sha256(self.origin.encode()).hexdigest()
        self.path = self.directory / f"{key}.{profile}.json"
        self.lock_path = self.directory / f"{key}.{profile}.lock"

    def _private(self, path):
        checked_path(path)
        info = path.stat()
        if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise AuthenticationRequired("Credential storage must belong to this user with owner-only permissions")

    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._private(self.directory)
        if not self.lock_path.exists():
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        self._private(self.lock_path)
        return file_lock(self.lock_path)

    def load(self):
        if not self.path.exists():
            return None
        self._private(self.directory)
        self._private(self.path)
        with self.path.open("rb") as stream:
            raw = stream.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise AuthenticationRequired("Credential document exceeds its size limit")
        try:
            value = json.loads(raw)
            if value["schema"] != SCHEMA or value["origin"] != self.origin:
                raise ValueError("identity mismatch")
            content = base64.b64decode(value["protected"], validate=True)
            if value["protection"] == "windows-dpapi" and os.name == "nt":
                content = _dpapi(content, decrypt=True)
            elif value["protection"] != "posix-private" or os.name == "nt":
                raise ValueError("protection mismatch")
            credential = json.loads(content)
            if not isinstance(credential, dict):
                raise TypeError("credential must be an object")
            if not isinstance(credential.get("access_token"), str) or not credential["access_token"]:
                raise ValueError("missing token")
            return credential
        except (ValueError, KeyError, TypeError) as error:
            raise AuthenticationRequired("Invalid protected credentials; run threemind auth login") from error

    def save_locked(self, value):
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        protected = _dpapi(content) if os.name == "nt" else content
        document = {"schema": SCHEMA, "origin": self.origin,
                    "protection": "windows-dpapi" if os.name == "nt" else "posix-private",
                    "protected": base64.b64encode(protected).decode()}
        temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(json.dumps(document).encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            if os.name != "nt":
                descriptor = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, value):
        with self.locked():
            self.save_locked(value)

    def clear(self):
        with self.locked():
            self.path.unlink(missing_ok=True)

    @staticmethod
    def metadata(value):
        return {key: item for key, item in (value or {}).items() if key != "access_token"}


def connection_arguments(parser, *, request_id=False):
    parser.add_argument("--url", default=os.getenv("THREEMIND_API_URL", "http://127.0.0.1:8877"))
    parser.add_argument("--username", default=os.getenv("THREEMIND_API_USERNAME"))
    parser.add_argument("--auth-profile", default=os.getenv("THREEMIND_AUTH_PROFILE", "default"))
    parser.add_argument("--auth-dir", type=Path, help="Host-owned protected credential directory")
    parser.add_argument("--execution-source", choices=SOURCES, default=os.getenv("THREEMIND_EXECUTION_SOURCE", "script"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--non-interactive", dest="interactive", action="store_false",
                       help="Return immediately when authentication is missing (default)")
    modes.add_argument("--interactive", action="store_true", help="Explicitly allow a local password prompt")
    parser.set_defaults(interactive=False)
    if request_id:
        from uuid import UUID

        parser.add_argument("--request-id", type=UUID)


def client_from_arguments(args):
    from .operations_client import OperationsClient

    return OperationsClient.from_environment(
        getattr(args, "url", None), username=getattr(args, "username", None),
        profile=getattr(args, "auth_profile", None), directory=getattr(args, "auth_dir", None),
        source=getattr(args, "execution_source", None), interactive=getattr(args, "interactive", False),
    )
