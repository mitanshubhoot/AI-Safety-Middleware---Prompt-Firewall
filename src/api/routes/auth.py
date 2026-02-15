"""Authentication endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import AuthManager, get_current_active_user
from src.config import get_settings
from src.db.session import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
settings = get_settings()


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response model."""

    user_id: str
    email: str
    role: str
    organization_id: str


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Args:
        request: Login credentials
        session: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # TODO: Implement actual user authentication from database
    # This is a placeholder that creates a token for demonstration
    
    logger.info("login_attempt", email=request.email)
    
    # For now, create a demo token
    # In production, verify against database
    token_data = {
        "sub": "demo-user-id",
        "email": request.email,
        "role": "user",
        "organization_id": "demo-org-id",
    }
    
    access_token = AuthManager.create_access_token(
        data=token_data,
        expires_delta=timedelta(hours=24)
    )
    
    logger.info("login_successful", email=request.email)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=86400,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user),
) -> UserResponse:
    """Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        User information
    """
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=current_user["role"],
        organization_id=current_user["organization_id"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: dict = Depends(get_current_active_user),
) -> TokenResponse:
    """Refresh JWT token.

    Args:
        current_user: Current authenticated user

    Returns:
        New JWT access token
    """
    token_data = {
        "sub": current_user["user_id"],
        "email": current_user["email"],
        "role": current_user["role"],
        "organization_id": current_user["organization_id"],
    }
    
    access_token = AuthManager.create_access_token(
        data=token_data,
        expires_delta=timedelta(hours=24)
    )
    
    logger.info("token_refreshed", user_id=current_user["user_id"])
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=86400,
    )
