"""Turn the tail of a failed step's log into a GitHub error annotation.

Annotations are readable through the public API without authentication; raw job logs are not. Usage:
    python .github/scripts/annotate_failure.py <title> <logfile> [max_lines]
Prefers lines that look like failures; falls back to the plain tail. Always exits 0 (diagnostic only).
"""
import re
import sys
from pathlib import Path

title, path = sys.argv[1], Path(sys.argv[2])
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
if not path.exists():
    print(f"::error title={title}::log file {path} was not produced")
    sys.exit(0)
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
key = re.compile(r"FAILED|ERROR|Error|error:|assert|Timeout|failed|passed|✘|›.*(fail|timed)", re.I)
picked = [ln for ln in lines if key.search(ln)][-limit:] or lines[-limit:]
body = "\n".join(ln[:300] for ln in picked)[:3500]
print(f"::error title={title}::" + body.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))
