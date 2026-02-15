"""Policy management service."""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.schemas import PolicyCreateRequest, PolicyResponse, PolicyUpdateRequest
from src.db.repositories.policy_repo import PolicyRepository
from src.utils.exceptions import PolicyException
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PolicyService:
    """Service for policy management operations."""

    def __init__(self, session: AsyncSession):
        """Initialize policy service.

        Args:
            session: Database session
        """
        self.session = session
        self.policy_repo = PolicyRepository(session)

    async def create_policy(self, request: PolicyCreateRequest) -> PolicyResponse:
        """Create a new policy.

        Args:
            request: Policy create request

        Returns:
            PolicyResponse with created policy
        """
        # Check if policy_id already exists
        existing = await self.policy_repo.get_by_policy_id(request.name.lower().replace(" ", "_"))
        if existing:
            raise PolicyException(
                f"Policy with similar ID already exists",
                {"policy_id": existing.policy_id},
            )

        policy = await self.policy_repo.create_policy(
            policy_id=request.name.lower().replace(" ", "_"),
            name=request.name,
            description=request.description,
            rules=request.rules,
            enabled=request.enabled,
        )

        await self.session.commit()

        logger.info("policy_created", policy_id=policy.policy_id, name=policy.name)

        return PolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            rules=policy.rules,
            enabled=policy.enabled,
            version=policy.version,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    async def update_policy(
        self,
        policy_id: str,
        request: PolicyUpdateRequest,
    ) -> PolicyResponse:
        """Update an existing policy.

        Args:
            policy_id: Policy ID to update
            request: Policy update request

        Returns:
            PolicyResponse with updated policy
        """
        policy = await self.policy_repo.update_policy(
            policy_id=policy_id,
            name=request.name,
            description=request.description,
            rules=request.rules,
            enabled=request.enabled,
        )

        if not policy:
            raise PolicyException(f"Policy not found: {policy_id}")

        await self.session.commit()

        logger.info("policy_updated", policy_id=policy_id, version=policy.version)

        return PolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            rules=policy.rules,
            enabled=policy.enabled,
            version=policy.version,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    async def get_policy(self, policy_id: str) -> PolicyResponse:
        """Get policy by ID.

        Args:
            policy_id: Policy ID

        Returns:
            PolicyResponse with policy data
        """
        policy = await self.policy_repo.get_by_policy_id(policy_id)

        if not policy:
            raise PolicyException(f"Policy not found: {policy_id}")

        return PolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            rules=policy.rules,
            enabled=policy.enabled,
            version=policy.version,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    async def list_policies(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PolicyResponse]:
        """List all policies.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of PolicyResponse objects
        """
        policies = await self.policy_repo.get_all(skip=skip, limit=limit)

        return [
            PolicyResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                rules=p.rules,
                enabled=p.enabled,
                version=p.version,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in policies
        ]

    async def get_active_policies(self) -> List[PolicyResponse]:
        """Get all active policies.

        Returns:
            List of active PolicyResponse objects
        """
        policies = await self.policy_repo.get_active_policies()

        return [
            PolicyResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                rules=p.rules,
                enabled=p.enabled,
                version=p.version,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in policies
        ]

    async def enable_policy(self, policy_id: str) -> PolicyResponse:
        """Enable a policy.

        Args:
            policy_id: Policy ID

        Returns:
            PolicyResponse with updated policy
        """
        success = await self.policy_repo.enable_policy(policy_id)

        if not success:
            raise PolicyException(f"Policy not found: {policy_id}")

        await self.session.commit()

        return await self.get_policy(policy_id)

    async def disable_policy(self, policy_id: str) -> PolicyResponse:
        """Disable a policy.

        Args:
            policy_id: Policy ID

        Returns:
            PolicyResponse with updated policy
        """
        success = await self.policy_repo.disable_policy(policy_id)

        if not success:
            raise PolicyException(f"Policy not found: {policy_id}")

        await self.session.commit()

        return await self.get_policy(policy_id)

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy.

        Args:
            policy_id: Policy ID

        Returns:
            True if deleted successfully
        """
        success = await self.policy_repo.delete_by_policy_id(policy_id)

        if not success:
            raise PolicyException(f"Policy not found: {policy_id}")

        await self.session.commit()

        logger.info("policy_deleted", policy_id=policy_id)

        return True
