"""Authentication API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest,
    RefreshRequest, TokenResponse, UserOut,
)
from app.services.auth_service import AuthService
from app.security.dependencies import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new citizen account."""
    service = AuthService(db)
    try:
        user = await service.register(data)
        logger.info("New user registered", email=data.email)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and get access/refresh tokens."""
    service = AuthService(db)
    result = await service.login(data.email, data.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
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
async def logout(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Invalidate the current session."""
    service = AuthService(db)
    await service.logout(current_user.user_id)
    return {"message": "Logged out successfully"}
