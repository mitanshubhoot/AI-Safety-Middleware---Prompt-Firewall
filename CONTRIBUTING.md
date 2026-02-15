# Contributing to AI Safety Middleware

Thank you for your interest in contributing to the AI Safety Middleware project! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Poetry (optional, for dependency management)

### Setup Development Environment

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ai-safety-middleware
```

2. **Install dependencies**:
```bash
# Using poetry
poetry install

# Or using pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. **Install pre-commit hooks**:
```bash
pre-commit install
```

4. **Start development services**:
```bash
docker-compose up -d postgres redis
```

5. **Run migrations**:
```bash
alembic upgrade head
```

6. **Seed database**:
```bash
python scripts/seed_database.py
```

## Development Workflow

### Branch Naming

- Features: `feature/description`
- Bug fixes: `fix/description`
- Documentation: `docs/description`
- Performance: `perf/description`

### Making Changes

1. **Create a new branch**:
```bash
git checkout -b feature/my-feature
```

2. **Make your changes** with proper tests and documentation

3. **Run code quality checks**:
```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run all checks
pre-commit run --all-files
```

4. **Run tests**:
```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_regex_detector.py -v
```

5. **Commit your changes**:
```bash
git add .
git commit -m "feat: add new detection pattern"
```

### Commit Message Format

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `perf:` Performance improvements
- `chore:` Maintenance tasks

Examples:
```
feat: add support for detecting GitHub tokens
fix: correct SSN validation regex pattern
docs: update API documentation with new endpoints
test: add unit tests for semantic detector
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line length**: 100 characters
- **Quotes**: Double quotes for strings
- **Type hints**: Required for all functions
- **Docstrings**: Google style

### Example

```python
"""Module docstring describing the module."""
from typing import List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MyClass:
    """Class docstring.

    Attributes:
        name: Description of name attribute
    """

    def __init__(self, name: str) -> None:
        """Initialize MyClass.

        Args:
            name: The name to use
        """
        self.name = name

    async def process(self, data: List[str]) -> Optional[dict]:
        """Process data asynchronously.

        Args:
            data: List of strings to process

        Returns:
            Processed result dictionary or None if failed

        Raises:
            ValueError: If data is empty
        """
        if not data:
            raise ValueError("Data cannot be empty")

        logger.info("processing_data", count=len(data))
        # Implementation here
        return {"result": "success"}
```

### Imports

Order imports in three groups:
1. Standard library
2. Third-party packages
3. Local imports

```python
# Standard library
import asyncio
from typing import List

# Third-party
from fastapi import FastAPI
from sqlalchemy import select

# Local
from src.config import get_settings
from src.utils.logging import get_logger
```

## Testing

### Writing Tests

Place tests in `tests/` directory matching source structure:

```
src/core/detection/regex_detector.py
tests/unit/test_regex_detector.py
```

### Test Guidelines

1. **Use descriptive names**:
```python
async def test_detect_openai_api_key():
    """Test detection of OpenAI API key pattern."""
```

2. **Use fixtures**:
```python
@pytest.fixture
def sample_prompt():
    return "My API key is sk-1234567890abcdef"
```

3. **Test edge cases**:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions

4. **Use assertions**:
```python
assert len(detections) > 0
assert detections[0].severity == Severity.CRITICAL
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_regex_detector.py

# Specific test function
pytest tests/unit/test_regex_detector.py::test_detect_openai_api_key

# With coverage
pytest --cov=src --cov-report=html

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Pull Request Process

### Before Submitting

1. ✅ All tests pass
2. ✅ Code is formatted (black)
3. ✅ No linter errors (ruff)
4. ✅ Type checks pass (mypy)
5. ✅ Documentation updated
6. ✅ Changelog entry added (if applicable)

### Creating PR

1. **Push your branch**:
```bash
git push origin feature/my-feature
```

2. **Create pull request** with:
   - Clear title and description
   - Reference related issues
   - Screenshots/examples if applicable
   - Testing instructions

3. **PR Template**:
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How to test these changes

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code follows style guide
- [ ] All tests pass
```

### Review Process

- At least one approval required
- All CI checks must pass
- Address review comments
- Squash commits before merge (if requested)

## Project Structure

```
src/
├── api/              # FastAPI routes and dependencies
├── core/             # Core business logic
│   ├── detection/    # Detection algorithms
│   ├── cache/        # Caching layer
│   └── models/       # Data models
├── db/               # Database layer
│   ├── models.py     # SQLAlchemy models
│   └── repositories/ # Repository pattern
├── services/         # Business logic services
└── utils/            # Utility functions

tests/
├── unit/             # Unit tests
├── integration/      # Integration tests
└── fixtures/         # Test fixtures

docs/                 # Documentation
config/               # Configuration files
scripts/              # Utility scripts
```

## Adding New Features

### Adding a New Detection Pattern

1. **Update patterns.yaml**:
```yaml
patterns:
  your_category:
    - name: pattern_name
      pattern: 'regex_pattern'
      description: "Description"
      severity: critical
```

2. **Add test**:
```python
@pytest.mark.asyncio
async def test_detect_new_pattern(detector):
    prompt = "Test prompt with pattern"
    detections = await detector.check(prompt)
    assert len(detections) > 0
```

3. **Update documentation**

### Adding a New API Endpoint

1. **Create route function**:
```python
@router.get("/new-endpoint")
async def new_endpoint() -> dict:
    """Endpoint description."""
    return {"status": "success"}
```

2. **Add tests**:
```python
async def test_new_endpoint(client):
    response = await client.get("/api/v1/new-endpoint")
    assert response.status_code == 200
```

3. **Update API.md documentation**

## Performance Considerations

- Use async/await for I/O operations
- Batch database operations where possible
- Cache frequently accessed data
- Profile before optimizing
- Add metrics for new features

## Documentation

- Update README.md for user-facing changes
- Update API.md for API changes
- Update ARCHITECTURE.md for design changes
- Add inline docstrings for all functions
- Include examples in documentation

## Questions?

- Open an issue for discussion
- Check existing issues and PRs
- Review documentation in `docs/`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎉
