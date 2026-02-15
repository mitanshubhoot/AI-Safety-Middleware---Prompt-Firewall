"""Repository for audit log records."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuditLog
from src.db.repositories.base_repo import BaseRepository
from src.utils.logging import get_logger
from src.utils.metrics import database_operations_total, database_query_duration_seconds

logger = get_logger(__name__)


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for audit log operations."""

    def __init__(self, session: AsyncSession):
        """Initialize audit log repository.

        Args:
            session: Async database session
        """
        super().__init__(AuditLog, session)

    async def create_log(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        status: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Create audit log entry.

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
            Created AuditLog instance
        """
        import time

        start = time.time()

        try:
            log = await self.create(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
            )

            duration = time.time() - start
            database_query_duration_seconds.labels(
                operation="create",
                table="audit_logs",
            ).observe(duration)

            database_operations_total.labels(
                operation="create",
                table="audit_logs",
                status="success",
            ).inc()

            logger.debug("audit_log_created", action=action, resource_type=resource_type)
            return log

        except Exception as e:
            database_operations_total.labels(
                operation="create",
                table="audit_logs",
                status="error",
            ).inc()
            logger.error("audit_log_creation_failed", error=str(e))
            raise

    async def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs by user ID.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of AuditLog instances
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_action(
        self,
        action: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs by action.

        Args:
            action: Action type
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of AuditLog instances
        """
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs by resource.

        Args:
            resource_type: Resource type
            resource_id: Resource ID (optional)
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of AuditLog instances
        """
        query = select(AuditLog).where(AuditLog.resource_type == resource_type)

        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)

        query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(
        self,
        hours: int = 24,
        limit: int = 1000,
    ) -> List[AuditLog]:
        """Get recent audit logs.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of records

        Returns:
            List of AuditLog instances
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.timestamp >= since)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_old_logs(self, days: int = 90) -> int:
        """Delete old audit logs.

        Args:
            days: Delete logs older than this many days

        Returns:
            Number of logs deleted
        """
        from sqlalchemy import delete

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            delete(AuditLog).where(AuditLog.timestamp < cutoff_date)
        )
        await self.session.flush()

        deleted = result.rowcount
        logger.info("old_audit_logs_deleted", count=deleted, days=days)
        return deleted

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
    ) -> List[AuditLog]:
        """Search audit logs with multiple filters.

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
            List of AuditLog instances
        """
        query = select(AuditLog)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if status:
            query = query.where(AuditLog.status == status)
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)

        query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())
