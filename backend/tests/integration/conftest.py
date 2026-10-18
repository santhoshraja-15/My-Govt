"""API-level fixtures: the real FastAPI app wired to the disposable test database."""
from __future__ import annotations

import uuid

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.security.jwt import create_access_token, hash_password

PASSWORD = "Str0ng-test-pass"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_factory(test_db_dsn):
    engine = create_async_engine(test_db_dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(session_factory):
    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(loop_scope="session")
async def make_staff(conn):
    """Create a non-citizen user (officer/admin) directly in the DB; returns (user_id, headers)."""
    async def _make(role: str, status: str = "active"):
        uid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO identity.app_user (user_id, email, password_hash, role, status) VALUES ($1,$2,$3,$4,$5)",
            uid, f"{role}-{uid.hex[:8]}@example.com", hash_password(PASSWORD), role, status,
        )
        return uid, auth(create_access_token({"sub": str(uid), "role": role}))

    return _make


@pytest_asyncio.fixture(loop_scope="session")
async def make_citizen(client):
    """Register a citizen through the public API and log in; returns a dict."""
    async def _make(name: str = "Test Citizen"):
        email = f"citizen-{uuid.uuid4().hex[:10]}@example.com"
        r = await client.post("/api/v1/auth/register",
                              json={"email": email, "password": PASSWORD, "full_name": name})
        assert r.status_code == 201, r.text
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        body = login.json()
        return {"email": email, "user": r.json(), "login": body, "headers": auth(body["access_token"])}

    return _make
