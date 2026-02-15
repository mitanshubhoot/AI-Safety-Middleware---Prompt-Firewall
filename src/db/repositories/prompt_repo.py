"""Repository for prompt records."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Prompt
from src.db.repositories.base_repo import BaseRepository
from src.utils.logging import get_logger
from src.utils.metrics import database_operations_total, database_query_duration_seconds

logger = get_logger(__name__)


class PromptRepository(BaseRepository[Prompt]):
    """Repository for prompt operations."""

    def __init__(self, session: AsyncSession):
        """Initialize prompt repository.

        Args:
            session: Async database session
        """
        super().__init__(Prompt, session)

    async def create_prompt(
        self,
        content_hash: str,
        user_id: Optional[str],
        policy_id: str,
        status: str,
        is_safe: bool,
        latency_ms: float,
        detection_count: int,
        cached: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Prompt:
        """Create prompt record.

        Args:
            content_hash: SHA-256 hash of prompt content
            user_id: User ID (optional)
            policy_id: Policy ID used
            status: Validation status
            is_safe: Whether prompt is safe
            latency_ms: Processing latency in milliseconds
            detection_count: Number of detections
            cached: Whether result was cached
            context: Additional context

        Returns:
            Created Prompt instance
        """
        import time

        start = time.time()

        try:
            prompt = await self.create(
                content_hash=content_hash,
                user_id=user_id,
                policy_id=policy_id,
                status=status,
                is_safe=is_safe,
                latency_ms=latency_ms,
                detection_count=detection_count,
                cached=cached,
                context=context,
            )

            duration = time.time() - start
            database_query_duration_seconds.labels(
                operation="create",
                table="prompts",
            ).observe(duration)

            database_operations_total.labels(
                operation="create",
                table="prompts",
                status="success",
            ).inc()

            logger.debug("prompt_created", id=prompt.id, status=status)
            return prompt

        except Exception as e:
            database_operations_total.labels(
                operation="create",
                table="prompts",
                status="error",
            ).inc()
            logger.error("prompt_creation_failed", error=str(e))
            raise

    async def get_by_content_hash(self, content_hash: str) -> Optional[Prompt]:
        """Get prompt by content hash.

        Args:
            content_hash: Content hash to search for

        Returns:
            Prompt instance or None if not found
        """
        result = await self.session.execute(
            select(Prompt).where(Prompt.content_hash == content_hash).order_by(Prompt.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Prompt]:
        """Get prompts by user ID.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of Prompt instances
        """
        result = await self.session.execute(
            select(Prompt)
            .where(Prompt.user_id == user_id)
            .order_by(Prompt.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get prompt statistics.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with statistics
        """
        query = select(
            func.count(Prompt.id).label("total"),
            func.count(Prompt.id).filter(Prompt.is_safe == True).label("safe"),  # noqa: E712
            func.count(Prompt.id).filter(Prompt.is_safe == False).label("blocked"),  # noqa: E712
            func.avg(Prompt.latency_ms).label("avg_latency"),
            func.count(Prompt.id).filter(Prompt.cached == True).label("cached"),  # noqa: E712
        )

        if start_date:
            query = query.where(Prompt.created_at >= start_date)
        if end_date:
            query = query.where(Prompt.created_at <= end_date)

        result = await self.session.execute(query)
        row = result.one()

        return {
            "total_prompts": row.total or 0,
            "safe_prompts": row.safe or 0,
            "blocked_prompts": row.blocked or 0,
            "avg_latency_ms": float(row.avg_latency) if row.avg_latency else 0.0,
            "cached_prompts": row.cached or 0,
            "cache_hit_rate": (row.cached / row.total) if row.total else 0.0,
        }

    async def get_recent_blocked(
        self,
        limit: int = 100,
        hours: int = 24,
    ) -> List[Prompt]:
        """Get recently blocked prompts.

        Args:
            limit: Maximum number of records
            hours: Number of hours to look back

        Returns:
            List of Prompt instances
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(Prompt)
            .where(Prompt.is_safe == False)  # noqa: E712
            .where(Prompt.created_at >= since)
            .order_by(Prompt.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_old_records(self, days: int = 90) -> int:
        """Delete old prompt records.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of records deleted
        """
        from sqlalchemy import delete

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            delete(Prompt).where(Prompt.created_at < cutoff_date)
        )
        await self.session.flush()

        deleted = result.rowcount
        logger.info("old_prompts_deleted", count=deleted, days=days)
        return deleted
