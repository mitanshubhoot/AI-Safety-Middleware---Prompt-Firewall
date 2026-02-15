"""Audit logging service."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.schemas import AuditLogEntry
from src.db.repositories.audit_repo import AuditLogRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """Service for audit logging operations."""

    def __init__(self, session: AsyncSession):
        """Initialize audit service.

        Args:
            session: Database session
        """
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    async def log_event(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Log an audit event.

        Args:
            user_id: User ID (optional)
            action: Action performed
            resource_type: Resource type
            resource_id: Resource ID (optional)
            status: Action status
            ip_address: Client IP address (optional)
            user_agent: Client user agent (optional)
            details: Additional details (optional)

        Returns:
            AuditLogEntry with logged event
        """
        log = await self.audit_repo.create_log(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

        await self.session.commit()

        return AuditLogEntry(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            status=log.status,
            details=log.details,
        )

    async def get_user_logs(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Get audit logs for a user.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of AuditLogEntry objects
        """
        logs = await self.audit_repo.get_by_user(user_id, skip, limit)

        return [
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                status=log.status,
                details=log.details,
            )
            for log in logs
        ]

    async def get_recent_logs(
        self,
        hours: int = 24,
        limit: int = 1000,
    ) -> List[AuditLogEntry]:
        """Get recent audit logs.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of records

        Returns:
            List of AuditLogEntry objects
        """
        logs = await self.audit_repo.get_recent(hours, limit)

        return [
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                status=log.status,
                details=log.details,
            )
            for log in logs
        ]

    async def search_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Search audit logs with filters.

        Args:
            user_id: User ID filter (optional)
            action: Action filter (optional)
            resource_type: Resource type filter (optional)
            status: Status filter (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of AuditLogEntry objects
        """
        logs = await self.audit_repo.search_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )

        return [
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                status=log.status,
                details=log.details,
            )
            for log in logs
        ]

    async def cleanup_old_logs(self, days: int = 90) -> int:
        """Delete old audit logs.

        Args:
            days: Delete logs older than this many days

        Returns:
            Number of logs deleted
        """
        count = await self.audit_repo.delete_old_logs(days)
        await self.session.commit()
        return count
