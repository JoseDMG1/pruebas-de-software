"""Generate ignored credentials/config for the isolated localhost Moodle site."""
import re
import secrets
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[2]
rag_env = root / "rag-service/.env"
if not rag_env.exists():
    raise SystemExit("Configure rag-service/.env first; an existing file is never overwritten.")
content = rag_env.read_text()
match = re.search(r"^MOODLE_SERVICE_SECRET=(.+)$", content, re.MULTILINE)
secret = match.group(1).strip().strip("\"'") if match else ""
moodle_env = root / ".moodle.env"
if moodle_env.exists():
    values = dict(line.split("=", 1) for line in moodle_env.read_text().splitlines() if "=" in line)
    existing = values["MOODLE_RAG_SHARED_SECRET"]
    if secret and existing != secret:
        raise SystemExit("Moodle and RAG secrets differ; reconcile their local env files first.")
    secret = existing
else:
    secret = secret if len(secret) >= 32 else secrets.token_hex(32)
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "MOODLE_RAG_URL": "http://127.0.0.1:8000",
        "MOODLE_RAG_SHARED_SECRET": secret,
        "MOODLE_DEMO_PASSWORD": "Aa1!" + secrets.token_urlsafe(16),
    }
    moodle_env.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    moodle_env.chmod(0o600)
if not match or match.group(1).strip().strip("\"'") != secret:
    content = re.sub(r"^MOODLE_SERVICE_SECRET=.*\n?", "", content, flags=re.MULTILINE)
    rag_env.write_text(content.rstrip() + "\nMOODLE_SERVICE_SECRET=" + secret + "\n")
    rag_env.chmod(0o600)
config = root / "moodle/config.php"
if not config.exists():
    shutil.copyfile(root / "dev/moodle/config.php", config)
local = root / ".local"
local.mkdir(exist_ok=True)
credentials = local / "sprint2-credentials.md"
credentials.write_text(
    "Local test site: http://127.0.0.1:8088\n\n"
    "Users: admin_sprint2, estudiante1, estudiante2, docente1, autoridad1\n\n"
    "Password: " + values["MOODLE_DEMO_PASSWORD"] + "\n"
)
credentials.chmod(0o600)
print("Local configuration ready. Credentials: .local/sprint2-credentials.md")
