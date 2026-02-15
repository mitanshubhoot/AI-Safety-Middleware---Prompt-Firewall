"""Authentication and authorization utilities."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


class AuthManager:
    """Manager for authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(
        data: dict,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create JWT access token.

        Args:
            data: Data to encode in token
            expires_delta: Token expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and verify JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload

        Raises:
            JWTError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            return payload
        except JWTError as e:
            logger.error("jwt_decode_error", error=str(e))
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User information from token

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = AuthManager.decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        logger.debug("user_authenticated", user_id=user_id)
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
            "organization_id": payload.get("organization_id"),
        }
    
    except JWTError:
        raise credentials_exception


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Active user information

    Raises:
        HTTPException: If user is inactive
    """
    if current_user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


def require_role(required_role: str):
    """Dependency to require specific role.

    Args:
        required_role: Role required to access endpoint

    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: dict = Depends(get_current_active_user),
    ) -> dict:
        """Check if user has required role.

        Args:
            current_user: Current authenticated user

        Returns:
            User information if authorized

        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.get("role") != required_role:
            logger.warning(
                "insufficient_permissions",
                user_id=current_user.get("user_id"),
                required_role=required_role,
                actual_role=current_user.get("role"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return current_user
    
    return role_checker
