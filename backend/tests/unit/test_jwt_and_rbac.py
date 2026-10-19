"""JWT validity/expiry and role-based access control (no database)."""
import base64
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt

from app.core.config import settings
from app.security import dependencies
from app.security.jwt import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)


def test_access_token_roundtrip():
    payload = decode_token(create_access_token({"sub": "u1", "role": "citizen"}))
    assert payload["sub"] == "u1" and payload["type"] == "access"


def test_refresh_token_is_typed_refresh():
    assert decode_token(create_refresh_token({"sub": "u1"}))["type"] == "refresh"


def test_expired_token_rejected():
    assert decode_token(create_access_token({"sub": "u1"}, timedelta(seconds=-5))) is None


def test_tampered_token_rejected():
    token = create_access_token({"sub": "u1"})
    assert decode_token(token[:-2] + ("AA" if token[-2:] != "AA" else "BB")) is None


def test_token_signed_with_other_secret_rejected():
    forged = jwt.encode({"sub": "u1", "type": "access"}, "another-secret-key-that-is-long-enough-0123456789", algorithm=settings.JWT_ALGORITHM)
    assert decode_token(forged) is None


def test_unsigned_alg_none_token_rejected():
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'u1', 'type': 'access'})}."
    assert decode_token(token) is None


def test_garbage_token_rejected():
    assert decode_token("not-a-jwt") is None


def test_password_hash_verifies_and_is_salted():
    h1, h2 = hash_password("S3cret-pass"), hash_password("S3cret-pass")
    assert h1 != h2 and verify_password("S3cret-pass", h1) and not verify_password("wrong", h1)


# -- RBAC: _get_user_from_token is patched, so no DB is needed --------------------------
def _creds(token="x"):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def as_user(monkeypatch):
    def _set(user):
        async def fake(credentials, db):
            return user

        monkeypatch.setattr(dependencies, "_get_user_from_token", fake)

    return _set


@pytest.mark.asyncio
async def test_require_role_allows_listed_role(as_user):
    as_user(SimpleNamespace(role="state_admin"))
    dep = dependencies.require_role(["state_admin", "system_admin"])
    assert (await dep(credentials=_creds(), db=None)).role == "state_admin"


@pytest.mark.asyncio
async def test_require_role_forbids_other_role(as_user):
    as_user(SimpleNamespace(role="citizen"))
    with pytest.raises(HTTPException) as e:
        await dependencies.require_role(["state_admin"])(credentials=_creds(), db=None)
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_unauthenticated_is_401(as_user):
    as_user(None)
    with pytest.raises(HTTPException) as e:
        await dependencies.require_role(["state_admin"])(credentials=None, db=None)
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_requires_authentication(as_user):
    as_user(None)
    with pytest.raises(HTTPException) as e:
        await dependencies.get_current_user(credentials=None, db=None)
    assert e.value.status_code == 401 and e.value.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_refresh_token_not_accepted_as_access_token():
    class _DB:  # must never be queried: the token-type check fails first
        async def execute(self, *a, **k):
            raise AssertionError("DB should not be hit for a refresh token")

    refresh = create_refresh_token({"sub": "u1"})
    assert await dependencies._get_user_from_token(_creds(refresh), _DB()) is None
