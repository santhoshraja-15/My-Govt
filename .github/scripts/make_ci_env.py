"""Create a throw-away `.env` for the CI Compose job from `.env.example`.

Every placeholder value (anything containing "change") gets a fresh random token, so no real or reused credential is
involved; NEO4J_AUTH is kept consistent with NEO4J_PASSWORD. The file is never printed.
"""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[2]
values: dict[str, str] = {}
lines = []
for raw in (root / ".env.example").read_text(encoding="utf-8").splitlines():
    if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
        key, _, val = raw.partition("=")
        if "change" in val.lower():
            val = secrets.token_hex(24)
        values[key] = val
        raw = f"{key}={val}"
    lines.append(raw)
if "NEO4J_PASSWORD" in values:
    lines = [f"NEO4J_AUTH=neo4j/{values['NEO4J_PASSWORD']}" if ln.startswith("NEO4J_AUTH=") else ln for ln in lines]
(root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote .env with {len(values)} variables ({sum('change' in v.lower() for v in values.values())} placeholders left)")
