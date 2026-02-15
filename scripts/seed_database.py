"""Seed database with initial data."""
import asyncio
import json

from src.config import get_settings
from src.db.repositories.policy_repo import PolicyRepository
from src.db.repositories.prompt_repo import PromptRepository
from src.db.session import AsyncSessionLocal
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


async def seed_policies() -> None:
    """Seed database with default policies."""
    logger.info("seeding_policies")

    async with AsyncSessionLocal() as session:
        policy_repo = PolicyRepository(session)

        # Create default policy
        default_policy = await policy_repo.create_policy(
            policy_id="default_policy",
            name="Default Security Policy",
            description="Standard security checks for all prompts",
            rules={
                "rules": [
                    {
                        "type": "block_pii",
                        "enabled": True,
                        "severity": "critical",
                        "action": "block",
                        "categories": ["ssn", "credit_card"],
                    },
                    {
                        "type": "block_credentials",
                        "enabled": True,
                        "severity": "critical",
                        "action": "block",
                        "categories": ["api_keys", "private_keys", "tokens", "passwords"],
                    },
                ]
            },
            enabled=True,
        )

        # Create strict policy
        strict_policy = await policy_repo.create_policy(
            policy_id="strict_policy",
            name="Strict Production Policy",
            description="Maximum security for production workloads",
            rules={
                "rules": [
                    {
                        "type": "block_all_pii",
                        "enabled": True,
                        "severity": "critical",
                        "action": "block",
                        "categories": ["ssn", "credit_card", "email", "phone_us"],
                    },
                    {
                        "type": "block_all_credentials",
                        "enabled": True,
                        "severity": "critical",
                        "action": "block",
                        "categories": ["api_keys", "private_keys", "tokens", "passwords"],
                    },
                ]
            },
            enabled=True,
        )

        # Create permissive policy
        permissive_policy = await policy_repo.create_policy(
            policy_id="permissive_policy",
            name="Permissive Development Policy",
            description="Relaxed policy for development environments",
            rules={
                "rules": [
                    {
                        "type": "warn_critical_only",
                        "enabled": True,
                        "severity": "critical",
                        "action": "warn",
                        "categories": ["api_keys", "private_keys"],
                    }
                ]
            },
            enabled=True,
        )

        await session.commit()

        logger.info(
            "policies_seeded",
            count=3,
            policies=[
                default_policy.policy_id,
                strict_policy.policy_id,
                permissive_policy.policy_id,
            ],
        )


async def seed_sample_patterns() -> None:
    """Seed sensitive data patterns for semantic detection."""
    logger.info("seeding_sample_patterns")

    from src.core.detection.semantic_detector import SemanticDetector

    detector = SemanticDetector()
    await detector.initialize()

    # Sample sensitive patterns
    patterns = [
        {
            "pattern_id": "aws_creds_1",
            "pattern_text": "Here are my AWS credentials: AKIAIOSFODNN7EXAMPLE",
            "category": "api_keys",
            "severity": "critical",
            "metadata": {"type": "aws_credentials"},
        },
        {
            "pattern_id": "openai_key_1",
            "pattern_text": "My OpenAI API key is sk-proj-1234567890abcdef",
            "category": "api_keys",
            "severity": "critical",
            "metadata": {"type": "openai_key"},
        },
        {
            "pattern_id": "password_leak_1",
            "pattern_text": "The admin password is SuperSecret123!",
            "category": "passwords",
            "severity": "critical",
            "metadata": {"type": "password_disclosure"},
        },
        {
            "pattern_id": "ssn_example_1",
            "pattern_text": "My social security number is 123-45-6789",
            "category": "pii",
            "severity": "critical",
            "metadata": {"type": "ssn"},
        },
        {
            "pattern_id": "credit_card_1",
            "pattern_text": "Use this card: 4532-1234-5678-9010",
            "category": "pii",
            "severity": "critical",
            "metadata": {"type": "credit_card"},
        },
    ]

    for pattern in patterns:
        await detector.add_sensitive_pattern(
            pattern_id=pattern["pattern_id"],
            pattern_text=pattern["pattern_text"],
            category=pattern["category"],
            severity=pattern["severity"],
            metadata=pattern["metadata"],
        )

    count = await detector.get_embedding_count()
    logger.info("sample_patterns_seeded", count=count)


async def main() -> None:
    """Main seeding function."""
    logger.info("starting_database_seeding")

    try:
        # Seed policies
        await seed_policies()

        # Seed sample patterns
        await seed_sample_patterns()

        logger.info("database_seeding_completed")

    except Exception as e:
        logger.error("database_seeding_failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
