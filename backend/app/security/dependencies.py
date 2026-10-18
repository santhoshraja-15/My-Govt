"""FastAPI security dependencies — authentication and authorization."""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.security.jwt import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def _get_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
) -> Optional[object]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(
        text("""
            SELECT u.user_id, u.email, u.role, u.status, u.citizen_id
            FROM identity.app_user u
            WHERE u.user_id = :uid AND u.status = 'active'
        """),
        {"uid": user_id},
    )
    row = result.fetchone()
    if not row:
        return None

    class UserContext:
        def __init__(self, r):
            self.user_id = r.user_id
            self.email = r.email
            self.role = r.role
            self.status = r.status
            self.citizen_id = r.citizen_id

    return UserContext(row)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user_from_token(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[object]:
    return await _get_user_from_token(credentials, db)


def require_role(allowed_roles: list[str]):
    async def _dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db),
    ):
        user = await _get_user_from_token(credentials, db)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dependency
