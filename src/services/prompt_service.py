"""Prompt validation service."""
import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.detection.detector_pipeline import DetectorPipeline, get_detector_pipeline
from src.core.models.schemas import PromptValidationRequest, ValidationResult
from src.db.repositories.detection_repo import DetectionRepository
from src.db.repositories.prompt_repo import PromptRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PromptService:
    """Service for prompt validation operations."""

    def __init__(
        self,
        session: AsyncSession,
        pipeline: Optional[DetectorPipeline] = None,
    ):
        """Initialize prompt service.

        Args:
            session: Database session
            pipeline: Detector pipeline (optional)
        """
        self.session = session
        self.prompt_repo = PromptRepository(session)
        self.detection_repo = DetectionRepository(session)
        self._pipeline = pipeline

    async def _get_pipeline(self) -> DetectorPipeline:
        """Get detector pipeline instance."""
        if self._pipeline is None:
            self._pipeline = await get_detector_pipeline()
        return self._pipeline

    async def validate_prompt(
        self,
        request: PromptValidationRequest,
    ) -> ValidationResult:
        """Validate a prompt.

        Args:
            request: Prompt validation request

        Returns:
            ValidationResult with detections and policy decision
        """
        pipeline = await self._get_pipeline()

        # Validate prompt through pipeline
        result = await pipeline.validate(
            prompt=request.prompt,
            user_id=request.user_id,
            policy_id=request.policy_id,
            context=request.context,
        )

        # Store in database
        try:
            content_hash = hashlib.sha256(request.prompt.encode()).hexdigest()

            # Create prompt record
            prompt_record = await self.prompt_repo.create_prompt(
                content_hash=content_hash,
                user_id=request.user_id,
                policy_id=result.policy_id,
                status=result.status.value,
                is_safe=result.is_safe,
                latency_ms=result.latency_ms,
                detection_count=len(result.detections),
                cached=result.cached,
                context=request.context,
            )

            # Create detection records
            for detection in result.detections:
                await self.detection_repo.create_detection(
                    prompt_id=prompt_record.id,
                    detection_type=detection.detection_type.value,
                    matched_pattern=detection.matched_pattern,
                    confidence_score=detection.confidence_score,
                    severity=detection.severity.value,
                    category=detection.category,
                    blocked=not result.is_safe,
                    match_positions={"positions": detection.match_positions} if detection.match_positions else None,
                    metadata=detection.metadata,
                )

            await self.session.commit()

            logger.info(
                "prompt_validated_and_stored",
                prompt_id=str(prompt_record.id),
                status=result.status.value,
            )

        except Exception as e:
            logger.error("failed_to_store_prompt", error=str(e))
            await self.session.rollback()
            # Don't fail validation if storage fails

        return result

    async def batch_validate(
        self,
        requests: List[PromptValidationRequest],
    ) -> List[ValidationResult]:
        """Validate multiple prompts.

        Args:
            requests: List of validation requests

        Returns:
            List of ValidationResult objects
        """
        pipeline = await self._get_pipeline()

        # Convert to pipeline format
        prompts = [
            (req.prompt, req.user_id, req.policy_id, req.context)
            for req in requests
        ]

        # Validate through pipeline
        results = await pipeline.batch_validate(prompts)

        # Store in database (best effort)
        try:
            for req, result in zip(requests, results):
                content_hash = hashlib.sha256(req.prompt.encode()).hexdigest()

                prompt_record = await self.prompt_repo.create_prompt(
                    content_hash=content_hash,
                    user_id=req.user_id,
                    policy_id=result.policy_id,
                    status=result.status.value,
                    is_safe=result.is_safe,
                    latency_ms=result.latency_ms,
                    detection_count=len(result.detections),
                    cached=result.cached,
                    context=req.context,
                )

                # Store detections
                for detection in result.detections:
                    await self.detection_repo.create_detection(
                        prompt_id=prompt_record.id,
                        detection_type=detection.detection_type.value,
                        matched_pattern=detection.matched_pattern,
                        confidence_score=detection.confidence_score,
                        severity=detection.severity.value,
                        category=detection.category,
                        blocked=not result.is_safe,
                    )

            await self.session.commit()

        except Exception as e:
            logger.error("failed_to_store_batch_prompts", error=str(e))
            await self.session.rollback()

        return results

    async def get_statistics(
        self,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Get prompt validation statistics.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            Dictionary with statistics
        """
        stats = await self.prompt_repo.get_statistics(start_date, end_date)

        # Add detection statistics
        detection_stats = await self.detection_repo.get_statistics_by_type(
            start_date, end_date
        )

        stats["detections_by_type"] = detection_stats
        return stats
