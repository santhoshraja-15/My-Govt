"""Authentication API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest, LoginResponse, RefreshRequest, RegisterRequest, TokenResponse, UserOut,
)
from app.security.dependencies import get_current_user
from app.security.ratelimit import login_limiter, rate_limit, register_limiter
from app.services import audit
from app.services.auth_service import AuthService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit(register_limiter, "register"))])
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new citizen account."""
    service = AuthService(db)
    try:
        user = await service.register(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    logger.info("user_registered", user_id=str(user.user_id))   # never log the e-mail address
    await audit.record(db, action="USER_REGISTERED", entity_type="user",
                       entity_id=str(user.user_id), request=request)
    return user


@router.post("/login", response_model=LoginResponse,
             dependencies=[Depends(rate_limit(login_limiter, "login"))])
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and get access/refresh tokens."""
    service = AuthService(db)
    result = await service.login(data.email, data.password)
    if not result:
        await audit.record(
            db, action="LOGIN_LOCKED" if service.last_failure == "locked" else "LOGIN_FAILED",
            entity_type="user", entity_id=audit.pseudonymise(data.email), request=request,
            new={"reason": service.last_failure}, outcome="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",      # identical for unknown user / wrong password / lockout
            headers={"WWW-Authenticate": "Bearer"},
        )
    await audit.record(db, action="LOGIN_SUCCESS", entity_type="user",
                       entity_id=str(result.user.user_id), user=result.user, request=request)
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    service = AuthService(db)
    result = await service.refresh(data.refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return result


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user


@router.post("/logout")
async def logout(request: Request, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.logout(current_user.user_id)
    await audit.record(db, action="LOGOUT", entity_type="user", entity_id=str(current_user.user_id),
                       user=current_user, request=request)
    return {"message": "Logged out successfully"}
