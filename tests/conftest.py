"""Test configuration and fixtures."""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db.base import Base

settings = get_settings()

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://aifw_user:aifw_password@localhost:5432/aifw_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_prompts():
    """Sample prompts for testing."""
    return {
        "safe": [
            "What is the capital of France?",
            "Explain how photosynthesis works.",
            "Write a Python function to calculate factorial.",
        ],
        "unsafe": [
            "My API key is sk-1234567890abcdef",
            "My SSN is 123-45-6789",
            "The password is Admin123!",
        ],
    }
