"""FastAPI dependencies."""
from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.services.audit_service import AuditService
from src.services.policy_service import PolicyService
from src.services.prompt_service import PromptService


async def get_prompt_service(
    session: AsyncSession = next(get_db()),  # type: ignore
) -> PromptService:
    """Get prompt service dependency.

    Args:
        session: Database session

    Returns:
        PromptService instance
    """
    return PromptService(session)


async def get_policy_service(
    session: AsyncSession = next(get_db()),  # type: ignore
) -> PolicyService:
    """Get policy service dependency.

    Args:
        session: Database session

    Returns:
        PolicyService instance
    """
    return PolicyService(session)


async def get_audit_service(
    session: AsyncSession = next(get_db()),  # type: ignore
) -> AuditService:
    """Get audit service dependency.

    Args:
        session: Database session

    Returns:
        AuditService instance
    """
    return AuditService(session)


def get_client_ip(request: Request) -> str:
    """Get client IP address from request.

    Args:
        request: FastAPI request

    Returns:
        Client IP address
    """
    # Try X-Forwarded-For header first (for proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Try X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """Get user agent from request.

    Args:
        request: FastAPI request

    Returns:
        User agent string
    """
    return request.headers.get("User-Agent", "unknown")
