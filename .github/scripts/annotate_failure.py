"""Turn the tail of a failed step's log into a GitHub error annotation.

Annotations are readable through the public API without authentication; raw job logs are not. Usage:
    python .github/scripts/annotate_failure.py <title> <logfile> [max_lines] [raw]
Without "raw" it prefers lines that look like failures and falls back to the plain tail. With "raw" the last lines are
published unfiltered (use it for logs that are already a curated diagnostic). Always exits 0 (diagnostic only).
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")           # test names contain check marks; never fail on a console code page
title, path = sys.argv[1], Path(sys.argv[2])
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
raw = len(sys.argv) > 4 and sys.argv[4] == "raw"
if not path.exists():
    print(f"::error title={title}::log file {path} was not produced")
    sys.exit(0)
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
# Failure evidence only: passing test lines (which mention words like "violations") must not crowd it out.
key = re.compile(r"FAILED|✘|ERROR|Error|error:|assert|Timeout|Expected|Received|serious \(|critical \(|offenders|^E ", re.I)
if raw:
    picked = lines[-limit:]
else:
    picked = [ln for ln in lines if key.search(ln) and "✓" not in ln][-limit:] or lines[-limit:]
body = "\n".join(ln[: 900 if raw else 300] for ln in picked)[:3900]
print(f"::error title={title}::" + body.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))
