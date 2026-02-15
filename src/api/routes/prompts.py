"""Prompt validation endpoints."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_client_ip, get_user_agent
from src.core.models.schemas import (
    BatchValidationRequest,
    BatchValidationResult,
    PromptValidationRequest,
    StatisticsResponse,
    ValidationResult,
)
from src.db.session import get_db
from src.services.audit_service import AuditService
from src.services.prompt_service import PromptService
from src.utils.exceptions import ValidationException
from src.utils.logging import get_logger

router = APIRouter(prefix="/prompts", tags=["Prompts"])
logger = get_logger(__name__)


@router.post("/validate", response_model=ValidationResult, status_code=status.HTTP_200_OK)
async def validate_prompt(
    request_data: PromptValidationRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> ValidationResult:
    """Validate a single prompt.

    Args:
        request_data: Prompt validation request
        request: FastAPI request
        session: Database session

    Returns:
        ValidationResult with detections and policy decision

    Raises:
        HTTPException: If validation fails
    """
    try:
        prompt_service = PromptService(session)
        result = await prompt_service.validate_prompt(request_data)

        # Log audit event
        audit_service = AuditService(session)
        await audit_service.log_event(
            user_id=request_data.user_id,
            action="validate_prompt",
            resource_type="prompt",
            resource_id=str(result.request_id),
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            details={
                "policy_id": result.policy_id,
                "is_safe": str(result.is_safe),
                "detections": str(len(result.detections)),
            },
        )

        return result

    except ValidationException as e:
        logger.error("validation_failed", error=str(e), details=e.details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message,
        )
    except Exception as e:
        logger.error("unexpected_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/validate/batch", response_model=BatchValidationResult, status_code=status.HTTP_200_OK)
async def batch_validate_prompts(
    request_data: BatchValidationRequest,
    session: AsyncSession = Depends(get_db),
) -> BatchValidationResult:
    """Validate multiple prompts in batch.

    Args:
        request_data: Batch validation request
        session: Database session

    Returns:
        BatchValidationResult with results for all prompts

    Raises:
        HTTPException: If validation fails
    """
    try:
        import time

        start_time = time.time()

        prompt_service = PromptService(session)
        results = await prompt_service.batch_validate(request_data.prompts)

        total_latency_ms = (time.time() - start_time) * 1000

        return BatchValidationResult(
            results=results,
            total_latency_ms=total_latency_ms,
        )

    except Exception as e:
        logger.error("batch_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch validation failed",
        )


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    session: AsyncSession = Depends(get_db),
) -> StatisticsResponse:
    """Get prompt validation statistics.

    Args:
        session: Database session

    Returns:
        StatisticsResponse with statistics

    Raises:
        HTTPException: If statistics retrieval fails
    """
    try:
        prompt_service = PromptService(session)
        stats = await prompt_service.get_statistics()

        return StatisticsResponse(
            total_prompts=stats.get("total_prompts", 0),
            total_detections=sum(stats.get("detections_by_type", {}).values()),
            blocked_prompts=stats.get("blocked_prompts", 0),
            cache_hit_rate=stats.get("cache_hit_rate", 0.0),
            avg_latency_ms=stats.get("avg_latency_ms", 0.0),
            detections_by_type=stats.get("detections_by_type", {}),
        )

    except Exception as e:
        logger.error("statistics_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics",
        )
