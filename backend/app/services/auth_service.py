"""Auth service — registration, login, token management."""
from typing import Optional
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import LoginResponse, RegisterRequest, TokenResponse, UserOut
from app.security.jwt import (
    create_access_token, create_refresh_token,
    decode_token, hash_password, verify_password,
)

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> UserOut:
        # Check email uniqueness
        existing = await self.db.execute(
            text("SELECT user_id FROM identity.app_user WHERE email = :email"),
            {"email": data.email},
        )
        if existing.fetchone():
            raise ValueError("Email already registered")

        user_id = uuid4()
        citizen_id = uuid4()

        # app_user first: identity.citizen.user_id references it
        await self.db.execute(
            text("""
                INSERT INTO identity.app_user (user_id, email, phone, password_hash, role, status)
                VALUES (:uid, :email, :phone, :pwd, 'citizen', 'active')
            """),
            {
                "uid": user_id,
                "email": data.email,
                "phone": data.phone,
                "pwd": hash_password(data.password),
            },
        )
        await self.db.execute(
            text("""
                INSERT INTO identity.citizen (citizen_id, user_id, name)
                VALUES (:cid, :uid, :name)
            """),
            {"cid": citizen_id, "uid": user_id, "name": data.full_name},
        )
        await self.db.commit()

        return UserOut(
            user_id=user_id,
            email=data.email,
            full_name=data.full_name,
            role="citizen",
            citizen_id=citizen_id,
        )

    async def login(self, email: str, password: str) -> Optional[LoginResponse]:
        result = await self.db.execute(
            text("""
                SELECT u.user_id, u.email, u.password_hash, u.role, u.status,
                       c.citizen_id, c.name AS full_name
                FROM identity.app_user u
                LEFT JOIN identity.citizen c ON c.user_id = u.user_id
                WHERE u.email = :email
            """),
            {"email": email},
        )
        row = result.fetchone()
        if not row:
            return None
        user_id, email_, pwd_hash, role, status, citizen_id, full_name = row

        if status != "active":
            return None
        if not verify_password(password, pwd_hash):
            await self.db.execute(
                text("UPDATE identity.app_user SET failed_logins = failed_logins + 1 WHERE user_id = :uid"),
                {"uid": user_id},
            )
            await self.db.commit()
            return None

        token_data = {"sub": str(user_id), "role": role}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        await self.db.execute(
            text("UPDATE identity.app_user SET failed_logins = 0 WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await self.db.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserOut(
                user_id=user_id,
                email=email_,
                full_name=full_name or "",
                role=role,
                citizen_id=citizen_id,
            ),
        )

    async def refresh(self, refresh_token: str) -> Optional[TokenResponse]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        role = payload.get("role", "citizen")
        if not user_id:
            return None
        # Verify user still active
        r = await self.db.execute(
            text("SELECT status FROM identity.app_user WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = r.fetchone()
        if not row or row[0] != "active":
            return None
        access_token = create_access_token({"sub": user_id, "role": role})
        return TokenResponse(access_token=access_token)

    async def logout(self, user_id) -> None:
        # Future: token blocklist in Redis
        pass
