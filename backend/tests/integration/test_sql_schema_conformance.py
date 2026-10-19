"""Every static SQL string in app/ must PREPARE against the real schema.

Catches column/table mismatches between the services and database/schema/001_schema.sql
without needing fixtures for every endpoint. f-string (dynamic) SQL cannot be prepared
statically; it is listed and must be covered by endpoint-level tests.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import asyncpg
import pytest

APP = Path(__file__).resolve().parents[2] / "app"
PARAM = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")
# Errors that prove a code/schema mismatch (as opposed to "cannot infer a parameter type")
HARD = (
    asyncpg.UndefinedColumnError, asyncpg.UndefinedTableError, asyncpg.UndefinedFunctionError,
    asyncpg.UndefinedObjectError, asyncpg.PostgresSyntaxError, asyncpg.DatatypeMismatchError,
    asyncpg.AmbiguousColumnError, asyncpg.InvalidSchemaNameError, asyncpg.UndefinedParameterError,
)


def harvest() -> list[tuple[str, int, str]]:
    out = []
    for py in sorted(APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "text" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                out.append((str(py.relative_to(APP)), node.lineno, node.args[0].value))
    return out


def to_asyncpg(sql: str) -> str:
    names: dict[str, int] = {}

    def sub(m):
        return f"${names.setdefault(m.group(1), len(names) + 1)}"

    return PARAM.sub(sub, sql)


CASES = harvest()


def test_harvest_finds_sql():
    assert len(CASES) > 40, "SQL harvester found suspiciously few statements"


@pytest.mark.db
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("path,line,sql", CASES, ids=[f"{p}:{ln}" for p, ln, _ in CASES])
async def test_sql_prepares_against_schema(conn, has_postgis, path, line, sql):
    if not has_postgis and re.search(r"\bST_\w+", sql):
        pytest.skip("BLOCKED: statement uses PostGIS functions and the test server has no PostGIS")
    try:
        await conn.prepare(to_asyncpg(sql))
    except HARD as e:
        pytest.fail(f"{path}:{line}: {type(e).__name__}: {e}\n{sql.strip()[:400]}")
    except asyncpg.PostgresError as e:  # e.g. cannot infer parameter type: not a schema mismatch
        pytest.skip(f"inconclusive ({type(e).__name__}): {e}")
