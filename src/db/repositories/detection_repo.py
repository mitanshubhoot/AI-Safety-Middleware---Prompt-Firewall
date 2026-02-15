"""Repository for detection records."""
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DetectionRecord
from src.db.repositories.base_repo import BaseRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DetectionRepository(BaseRepository[DetectionRecord]):
    """Repository for detection records."""

    def __init__(self, session: AsyncSession):
        """Initialize detection repository.

        Args:
            session: Async database session
        """
        super().__init__(DetectionRecord, session)

    async def create_detection(
        self,
        prompt_id: UUID,
        detection_type: str,
        matched_pattern: str,
        confidence_score: float,
        severity: str,
        category: str | None,
        blocked: bool,
        match_positions: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DetectionRecord:
        """Create detection record.

        Args:
            prompt_id: Associated prompt ID
            detection_type: Type of detection
            matched_pattern: Pattern that matched
            confidence_score: Confidence score
            severity: Severity level
            category: Detection category
            blocked: Whether detection led to blocking
            match_positions: Match positions (optional)
            metadata: Additional metadata (optional)

        Returns:
            Created DetectionRecord instance
        """
        return await self.create(
            prompt_id=prompt_id,
            detection_type=detection_type,
            matched_pattern=matched_pattern,
            confidence_score=confidence_score,
            severity=severity,
            category=category,
            blocked=blocked,
            match_positions=match_positions,
            metadata=metadata,
        )

    async def get_by_prompt_id(self, prompt_id: UUID) -> List[DetectionRecord]:
        """Get all detections for a prompt.

        Args:
            prompt_id: Prompt ID

        Returns:
            List of DetectionRecord instances
        """
        result = await self.session.execute(
            select(DetectionRecord)
            .where(DetectionRecord.prompt_id == prompt_id)
            .order_by(DetectionRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_statistics_by_type(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Dict[str, int]:
        """Get detection statistics grouped by type.

        Args:
            start_date: Start date filter (optional)
            end_date: End date filter (optional)

        Returns:
            Dictionary with detection counts by type
        """
        query = select(
            DetectionRecord.detection_type,
            func.count(DetectionRecord.id).label("count"),
        ).group_by(DetectionRecord.detection_type)

        if start_date:
            query = query.where(DetectionRecord.created_at >= start_date)
        if end_date:
            query = query.where(DetectionRecord.created_at <= end_date)

        result = await self.session.execute(query)
        return {row.detection_type: row.count for row in result.all()}

    async def get_statistics_by_severity(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Dict[str, int]:
        """Get detection statistics grouped by severity.

        Args:
            start_date: Start date filter (optional)
            end_date: End date filter (optional)

        Returns:
            Dictionary with detection counts by severity
        """
        query = select(
            DetectionRecord.severity,
            func.count(DetectionRecord.id).label("count"),
        ).group_by(DetectionRecord.severity)

        if start_date:
            query = query.where(DetectionRecord.created_at >= start_date)
        if end_date:
            query = query.where(DetectionRecord.created_at <= end_date)

        result = await self.session.execute(query)
        return {row.severity: row.count for row in result.all()}

    async def get_top_patterns(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> List[tuple[str, int]]:
        """Get most frequently detected patterns.

        Args:
            limit: Maximum number of results
            days: Number of days to look back

        Returns:
            List of (pattern, count) tuples
        """
        since = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(
                DetectionRecord.matched_pattern,
                func.count(DetectionRecord.id).label("count"),
            )
            .where(DetectionRecord.created_at >= since)
            .group_by(DetectionRecord.matched_pattern)
            .order_by(func.count(DetectionRecord.id).desc())
            .limit(limit)
        )
        return [(row.matched_pattern, row.count) for row in result.all()]
