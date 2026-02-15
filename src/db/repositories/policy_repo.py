"""Repository for policy records."""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Policy
from src.db.repositories.base_repo import BaseRepository
from src.utils.logging import get_logger
from src.utils.metrics import database_operations_total, database_query_duration_seconds

logger = get_logger(__name__)


class PolicyRepository(BaseRepository[Policy]):
    """Repository for policy operations."""

    def __init__(self, session: AsyncSession):
        """Initialize policy repository.

        Args:
            session: Async database session
        """
        super().__init__(Policy, session)

    async def create_policy(
        self,
        policy_id: str,
        name: str,
        rules: Dict[str, Any],
        description: Optional[str] = None,
        enabled: bool = True,
    ) -> Policy:
        """Create policy record.

        Args:
            policy_id: Human-readable policy identifier
            name: Policy name
            rules: Policy rules in JSON format
            description: Policy description (optional)
            enabled: Whether policy is enabled

        Returns:
            Created Policy instance
        """
        import time

        start = time.time()

        try:
            policy = await self.create(
                policy_id=policy_id,
                name=name,
                description=description,
                rules=rules,
                enabled=enabled,
                version=1,
            )

            duration = time.time() - start
            database_query_duration_seconds.labels(
                operation="create",
                table="policies",
            ).observe(duration)

            database_operations_total.labels(
                operation="create",
                table="policies",
                status="success",
            ).inc()

            logger.info("policy_created", policy_id=policy_id, name=name)
            return policy

        except Exception as e:
            database_operations_total.labels(
                operation="create",
                table="policies",
                status="error",
            ).inc()
            logger.error("policy_creation_failed", error=str(e))
            raise

    async def get_by_policy_id(self, policy_id: str) -> Optional[Policy]:
        """Get policy by policy_id.

        Args:
            policy_id: Policy identifier

        Returns:
            Policy instance or None if not found
        """
        result = await self.session.execute(
            select(Policy).where(Policy.policy_id == policy_id)
        )
        return result.scalar_one_or_none()

    async def get_active_policies(self) -> List[Policy]:
        """Get all active policies.

        Returns:
            List of active Policy instances
        """
        result = await self.session.execute(
            select(Policy).where(Policy.enabled == True).order_by(Policy.name)  # noqa: E712
        )
        return list(result.scalars().all())

    async def update_policy(
        self,
        policy_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        rules: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[Policy]:
        """Update policy by policy_id.

        Args:
            policy_id: Policy identifier
            name: New name (optional)
            description: New description (optional)
            rules: New rules (optional)
            enabled: New enabled status (optional)

        Returns:
            Updated Policy instance or None if not found
        """
        policy = await self.get_by_policy_id(policy_id)
        if not policy:
            return None

        if name is not None:
            policy.name = name
        if description is not None:
            policy.description = description
        if rules is not None:
            policy.rules = rules
            policy.version += 1
        if enabled is not None:
            policy.enabled = enabled

        await self.session.flush()
        await self.session.refresh(policy)

        logger.info("policy_updated", policy_id=policy_id, version=policy.version)
        return policy

    async def enable_policy(self, policy_id: str) -> bool:
        """Enable a policy.

        Args:
            policy_id: Policy identifier

        Returns:
            True if enabled, False if not found
        """
        policy = await self.get_by_policy_id(policy_id)
        if policy:
            policy.enabled = True
            await self.session.flush()
            logger.info("policy_enabled", policy_id=policy_id)
            return True
        return False

    async def disable_policy(self, policy_id: str) -> bool:
        """Disable a policy.

        Args:
            policy_id: Policy identifier

        Returns:
            True if disabled, False if not found
        """
        policy = await self.get_by_policy_id(policy_id)
        if policy:
            policy.enabled = False
            await self.session.flush()
            logger.info("policy_disabled", policy_id=policy_id)
            return True
        return False

    async def delete_by_policy_id(self, policy_id: str) -> bool:
        """Delete policy by policy_id.

        Args:
            policy_id: Policy identifier

        Returns:
            True if deleted, False if not found
        """
        policy = await self.get_by_policy_id(policy_id)
        if policy:
            await self.session.delete(policy)
            await self.session.flush()
            logger.info("policy_deleted", policy_id=policy_id)
            return True
        return False
