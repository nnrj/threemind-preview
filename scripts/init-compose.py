"""Create local Compose secrets without replacing any existing configuration."""

import argparse
import base64
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "deploy/compose.env"
parser = argparse.ArgumentParser()
parser.add_argument(
    "--ensure-ai-key", action="store_true", help="Add an absent AI encryption key; preserve existing secrets"
)
args = parser.parse_args()
if args.ensure_ai_key:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not any(line.startswith("THREEMIND_SECRET_KEYS=") and line.split("=", 1)[1].strip() for line in lines):
        lines = [line for line in lines if not line.startswith("THREEMIND_SECRET_KEYS=")]
        lines.append("THREEMIND_SECRET_KEYS=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
else:
    with path.open("x", encoding="utf-8") as output:
        for key in ("THREEMIND_PG_ADMIN_PASSWORD", "THREEMIND_PG_OWNER_PASSWORD", "THREEMIND_PG_PASSWORD"):
            output.write(key + "=" + secrets.token_urlsafe(32) + "\n")
        output.write("THREEMIND_SECRET_KEYS=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() + "\n")
        output.write("THREEMIND_HTTP_PORT=8878\nTHREEMIND_MAX_ACTIVE_JOBS=2\n")
try:
    path.chmod(0o600)
except OSError:
    pass
print("Prepared ignored deploy/compose.env. Credentials were not printed.")
