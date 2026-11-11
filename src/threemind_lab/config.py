import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_url: str
    mode: str = "workstation"
    authentication: str = "session"
    origins: tuple[str, ...] = (
        "http://127.0.0.1:8877",
        "http://localhost:8877",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    )
    hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")
    secure_cookie: bool = False
    backend: str = "native"
    docs_root: Path = ROOT
    data_root: Path = ROOT / "data"
    checkpoint_backend: str = "database"
    max_active_jobs: int = 2
    max_run_seconds: int = 86400
    max_import_bytes: int = 512 * 1024 * 1024
    max_media_decoders: int = 2
    max_media_uploads: int = 4
    max_staged_media_bytes: int = 16384 * 1024 * 1024
    secret_keys: tuple[str, ...] = ()
    ai_allowed_origins: tuple[str, ...] = ()
    max_ai_jobs: int = 2
    max_notification_jobs: int = 1
    notification_allowed_endpoints: tuple[str, ...] = ()

    def __post_init__(self):
        if self.checkpoint_backend not in ("database", "filesystem") or not self.data_root.is_absolute():
            raise ValueError("invalid host data root/checkpoint backend")
        if self.mode not in ("workstation", "server") or self.backend not in ("native", "reference"):
            raise ValueError("invalid deployment/backend configuration")
        if self.authentication != "session":
            raise ValueError("Lab requires authenticated sessions; authentication must be 'session'")
        if not self.database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("Lab requires a PostgreSQL connection URL")
        if "*" in self.origins or "*" in self.hosts:
            raise ValueError("explicit hosts and origins are required")
        if (
            min(
                self.max_active_jobs,
                self.max_run_seconds,
                self.max_import_bytes,
                self.max_media_decoders,
                self.max_media_uploads,
                self.max_staged_media_bytes,
                self.max_ai_jobs,
                self.max_notification_jobs,
            )
            <= 0
        ):
            raise ValueError("deployment resource budgets must be positive")

    @classmethod
    def from_env(cls):
        load_env()
        url = os.environ.get("THREEMIND_DATABASE_URL")
        if not url and os.getenv("THREEMIND_PG_PASSWORD"):
            from urllib.parse import quote

            url = f"postgresql://{quote(os.getenv('THREEMIND_PG_USER', 'threemind_app'), safe='')}:{quote(os.environ['THREEMIND_PG_PASSWORD'], safe='')}@{os.getenv('THREEMIND_PG_HOST', '127.0.0.1')}:{os.getenv('THREEMIND_PG_PORT', '5433')}/{os.getenv('THREEMIND_PG_DATABASE', 'threemind')}"
        if not url:
            raise ValueError(
                "Database is not configured. Run threemind setup-local or configure .env; see docs/zh/v2-operations.md"
            )
        return cls(
            database_url=url,
            mode=os.getenv("THREEMIND_MODE", "workstation"),
            authentication=os.getenv("THREEMIND_AUTHENTICATION", "session"),
            origins=tuple(os.environ["THREEMIND_ORIGINS"].split(","))
            if "THREEMIND_ORIGINS" in os.environ
            else cls.origins,
            hosts=tuple(os.environ["THREEMIND_HOSTS"].split(",")) if "THREEMIND_HOSTS" in os.environ else cls.hosts,
            secure_cookie=os.getenv("THREEMIND_SECURE_COOKIE", "false") == "true",
            backend=os.getenv("THREEMIND_BACKEND", "native"),
            data_root=Path(os.getenv("THREEMIND_DATA_ROOT", str(ROOT / "data"))),
            checkpoint_backend=os.getenv("THREEMIND_CHECKPOINT_BACKEND", "database"),
            max_active_jobs=int(os.getenv("THREEMIND_MAX_ACTIVE_JOBS", "2")),
            max_run_seconds=int(os.getenv("THREEMIND_MAX_RUN_SECONDS", "86400")),
            max_import_bytes=int(os.getenv("THREEMIND_MAX_IMPORT_MB", "128")) * 1024 * 1024,
            max_media_decoders=int(os.getenv("THREEMIND_MAX_MEDIA_DECODERS", "2")),
            max_media_uploads=int(os.getenv("THREEMIND_MAX_MEDIA_UPLOADS", "4")),
            max_staged_media_bytes=int(os.getenv("THREEMIND_MAX_STAGED_MEDIA_MB", "16384")) * 1024 * 1024,
            secret_keys=tuple(k.strip() for k in os.getenv("THREEMIND_SECRET_KEYS", "").split(",") if k.strip()),
            ai_allowed_origins=tuple(
                k.strip() for k in os.getenv("THREEMIND_AI_ALLOWED_ORIGINS", "").split(",") if k.strip()
            ),
            max_ai_jobs=int(os.getenv("THREEMIND_MAX_AI_JOBS", "2")),
            max_notification_jobs=int(os.getenv("THREEMIND_MAX_NOTIFICATION_JOBS", "1")),
            notification_allowed_endpoints=tuple(
                value.strip().lower()
                for value in os.getenv("THREEMIND_NOTIFICATION_ALLOWED_ENDPOINTS", "").split(",")
                if value.strip()
            ),
        )
