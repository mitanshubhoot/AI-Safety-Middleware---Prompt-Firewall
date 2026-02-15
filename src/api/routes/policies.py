"""Policy management endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.schemas import (
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdateRequest,
)
from src.db.session import get_db
from src.services.policy_service import PolicyService
from src.utils.exceptions import PolicyException
from src.utils.logging import get_logger

router = APIRouter(prefix="/policies", tags=["Policies"])
logger = get_logger(__name__)


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    request_data: PolicyCreateRequest,
    session: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Create a new policy.

    Args:
        request_data: Policy create request
        session: Database session

    Returns:
        PolicyResponse with created policy

    Raises:
        HTTPException: If creation fails
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.create_policy(request_data)

    except PolicyException as e:
        logger.error("policy_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except Exception as e:
        logger.error("unexpected_policy_creation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create policy",
        )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    session: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Get policy by ID.

    Args:
        policy_id: Policy ID
        session: Database session

    Returns:
        PolicyResponse with policy data

    Raises:
        HTTPException: If policy not found
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.get_policy(policy_id)

    except PolicyException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except Exception as e:
        logger.error("policy_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policy",
        )


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    request_data: PolicyUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Update an existing policy.

    Args:
        policy_id: Policy ID
        request_data: Policy update request
        session: Database session

    Returns:
        PolicyResponse with updated policy

    Raises:
        HTTPException: If update fails
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.update_policy(policy_id, request_data)

    except PolicyException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except Exception as e:
        logger.error("policy_update_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update policy",
        )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a policy.

    Args:
        policy_id: Policy ID
        session: Database session

    Raises:
        HTTPException: If deletion fails
    """
    try:
        policy_service = PolicyService(session)
        await policy_service.delete_policy(policy_id)

    except PolicyException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except Exception as e:
        logger.error("policy_deletion_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy",
        )


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
) -> PolicyListResponse:
    """List all policies.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records
        session: Database session

    Returns:
        PolicyListResponse with list of policies

    Raises:
        HTTPException: If listing fails
    """
    try:
        policy_service = PolicyService(session)
        policies = await policy_service.list_policies(skip, limit)

        return PolicyListResponse(
            policies=policies,
            total=len(policies),
        )

    except Exception as e:
        logger.error("policy_listing_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list policies",
        )


@router.get("/active/list", response_model=List[PolicyResponse])
async def get_active_policies(
    session: AsyncSession = Depends(get_db),
) -> List[PolicyResponse]:
    """Get all active policies.

    Args:
        session: Database session

    Returns:
        List of active PolicyResponse objects

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.get_active_policies()

    except Exception as e:
        logger.error("active_policies_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active policies",
        )


@router.post("/{policy_id}/enable", response_model=PolicyResponse)
async def enable_policy(
    policy_id: str,
    session: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Enable a policy.

    Args:
        policy_id: Policy ID
        session: Database session

    Returns:
        PolicyResponse with updated policy

    Raises:
        HTTPException: If enable fails
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.enable_policy(policy_id)

    except PolicyException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except Exception as e:
        logger.error("policy_enable_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable policy",
        )


@router.post("/{policy_id}/disable", response_model=PolicyResponse)
async def disable_policy(
    policy_id: str,
    session: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    """Disable a policy.

    Args:
        policy_id: Policy ID
        session: Database session

    Returns:
        PolicyResponse with updated policy

    Raises:
        HTTPException: If disable fails
    """
    try:
        policy_service = PolicyService(session)
        return await policy_service.disable_policy(policy_id)

    except PolicyException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except Exception as e:
        logger.error("policy_disable_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable policy",
        )
