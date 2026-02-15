# AI Safety Middleware - Prompt Firewall

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

AI safety middleware that intercepts and validates LLM prompts in real-time. Prevents data leaks, detects sensitive information, and enforces security policies before prompts reach LLM providers.

## ✨ Features

- **🚀 Sub-millisecond Latency**: Async request handling for <1ms validation
- **🔍 Multi-layered Detection**:
  - Regex-based pattern matching (API keys, PII, credentials)
  - RAG-powered semantic similarity detection
  - Policy-based rule engine
- **⚡ High Performance**: 50K+ prompts/hour capacity with Redis caching
- **📊 Production-Ready**: Docker/Docker Compose, health checks, metrics
- **🔐 Comprehensive Security**: Luhn validation, context-aware detection
- **📈 Observability**: Prometheus metrics, structured logging, audit trails
- **🎯 Type-Safe**: Full type hints with mypy strict mode

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│        FastAPI REST API             │
│  (+ gRPC Service Interfaces)        │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│      Detection Pipeline             │
│  ┌─────────────────────────────┐   │
│  │  1. Regex Detector          │   │
│  │  2. Semantic Detector       │   │  ← Redis/RediSearch
│  │  3. Policy Engine           │   │    (Vector Similarity)
│  └─────────────────────────────┘   │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│       PostgreSQL + Redis            │
│   (Audit Logs, Policies, Cache)    │
└─────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Poetry (optional, for dependency management)

### Using Docker Compose (Recommended)

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ai-safety-middleware
```

2. **Create environment file**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start all services**:
```bash
docker-compose up -d
```

4. **Run database migrations**:
```bash
docker-compose exec api python -m alembic upgrade head
```

5. **Seed database with initial data**:
```bash
docker-compose exec api python scripts/seed_database.py
```

6. **Verify services are running**:
```bash
curl http://localhost:8000/health
```

### API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Prometheus Metrics**: http://localhost:8000/metrics
- **RedisInsight**: http://localhost:8001

## 📋 API Examples

### Validate a Prompt

```bash
curl -X POST http://localhost:8000/api/v1/prompts/validate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France?",
    "user_id": "user_123",
    "policy_id": "default_policy"
  }'
```

**Response**:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "allowed",
  "is_safe": true,
  "detections": [],
  "policy_id": "default_policy",
  "latency_ms": 12.5,
  "timestamp": "2024-01-01T12:00:00Z",
  "message": "Prompt is safe",
  "cached": false
}
```

### Validate with Sensitive Data

```bash
curl -X POST http://localhost:8000/api/v1/prompts/validate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "My API key is sk-1234567890abcdef",
    "user_id": "user_123"
  }'
```

**Response**:
```json
{
  "request_id": "660e9500-f30c-42e5-b827-557766551111",
  "status": "blocked",
  "is_safe": false,
  "detections": [
    {
      "id": "770fa600-g41d-53f6-c938-668877662222",
      "detection_type": "regex",
      "matched_pattern": "openai_api_key",
      "confidence_score": 1.0,
      "severity": "critical",
      "category": "api_keys",
      "match_positions": [[14, 46]],
      "metadata": {
        "description": "OpenAI API Key"
      }
    }
  ],
  "policy_id": "default_policy",
  "latency_ms": 15.3,
  "timestamp": "2024-01-01T12:01:00Z",
  "message": "Blocked by rule 'block_credentials': openai_api_key (critical)",
  "cached": false
}
```

### Batch Validation

```bash
curl -X POST http://localhost:8000/api/v1/prompts/validate/batch \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": [
      {"prompt": "What is 2+2?"},
      {"prompt": "Explain quantum computing"}
    ]
  }'
```

### Get Statistics

```bash
curl http://localhost:8000/api/v1/prompts/statistics
```

## 🔍 Detection Capabilities

### Tier 1: Regex-Based Patterns

- **API Keys**: OpenAI, AWS, GCP, Azure, GitHub, Slack, Stripe
- **Private Keys**: RSA, OpenSSH, DSA, EC, PGP
- **Authentication**: JWT tokens, Bearer tokens, OAuth tokens
- **PII**: SSN, credit cards (with Luhn validation), emails, phone numbers
- **Network**: IP addresses, internal URLs
- **Database**: Connection strings, JDBC URLs
- **Passwords**: Context-aware password detection

### Tier 2: Semantic Detection

- Vector embeddings using sentence-transformers
- Cosine similarity search via RediSearch
- Detects semantically similar sensitive patterns
- Configurable similarity threshold (default: 0.85)
- Fuzzy matching for company-specific secrets

### Tier 3: Policy Engine

- YAML-based policy definitions
- Allow/deny lists with wildcards
- Contextual policies per department/user
- Policy versioning and rollback
- Actions: allow, block, warn, log

## 🐳 Docker Services

### Core Services

- **api**: FastAPI application with gRPC server (ports 8000, 50051)
- **postgres**: PostgreSQL 15 with pgvector extension
- **redis**: Redis Stack with RediSearch module

### Monitoring (Optional)

Start with monitoring stack:
```bash
docker-compose --profile monitoring up -d
```

- **prometheus**: Metrics collection (port 9090)
- **grafana**: Visualization dashboards (port 3000)

## 🛠️ Development

### Local Setup

1. **Install dependencies**:
```bash
poetry install
# or
pip install -r requirements.txt
```

2. **Set up pre-commit hooks**:
```bash
pre-commit install
```

3. **Run database locally**:
```bash
docker-compose up postgres redis -d
```

4. **Run migrations**:
```bash
alembic upgrade head
```

5. **Start development server**:
```bash
python -m src.main
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_regex_detector.py
```

### Code Quality

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

### Benchmarking

```bash
python scripts/benchmark.py
```

Expected performance:
- **Safe prompts**: ~10-20ms mean latency
- **Unsafe prompts**: ~15-30ms mean latency
- **Throughput**: 50-100 prompts/second (single worker)

## 📊 Monitoring & Metrics

### Prometheus Metrics

Available at `/metrics`:

- `prompt_validation_total`: Total validations by status and policy
- `prompt_validation_duration_seconds`: Validation latency histogram
- `detections_by_type_total`: Detections grouped by type/severity
- `cache_hit_rate`: Cache effectiveness
- `database_query_duration_seconds`: Database performance
- `redis_vector_search_duration_seconds`: Semantic search latency

### Structured Logging

JSON-formatted logs in production:
```json
{
  "event": "prompt_validated_and_stored",
  "prompt_id": "uuid",
  "status": "blocked",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "uuid"
}
```

## 🔐 Security Best Practices

1. **Secrets Management**:
   - Never commit `.env` files
   - Use Docker secrets in production
   - Rotate API keys regularly

2. **Network Security**:
   - Run behind a reverse proxy (nginx/Traefik)
   - Enable HTTPS/TLS
   - Restrict Redis/PostgreSQL ports

3. **Database Security**:
   - Use strong passwords
   - Enable SSL/TLS connections
   - Regular backups

4. **Audit Logging**:
   - All validations are logged
   - Retention: 90 days (configurable)
   - Includes IP addresses and user agents

## 📈 Performance Tuning

### Caching

- Enable Redis caching (default: on)
- Adjust TTL: `CACHE_TTL=3600` (seconds)
- Cache only safe results to avoid false negatives

### Database

- Connection pool size: `DATABASE_POOL_SIZE=20`
- Max overflow: `DATABASE_MAX_OVERFLOW=10`
- Use read replicas for analytics

### Detection

- Adjust semantic threshold: `SEMANTIC_THRESHOLD=0.85`
- Disable detectors not needed for your use case
- Batch process non-real-time validations

## 🗂️ Project Structure

```
ai-safety-middleware/
├── src/
│   ├── api/                 # FastAPI routes and dependencies
│   ├── core/                # Core detection logic
│   │   ├── detection/       # Detectors and pipeline
│   │   ├── cache/           # Redis client and vector store
│   │   └── models/          # Pydantic schemas and enums
│   ├── db/                  # Database models and repositories
│   ├── services/            # Business logic services
│   ├── utils/               # Utilities (logging, metrics, exceptions)
│   ├── grpc_services/       # gRPC service implementations
│   └── main.py              # FastAPI application entry point
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── protos/                  # gRPC protocol definitions
├── config/                  # Configuration files (patterns, policies)
├── scripts/                 # Utility scripts
├── docs/                    # Additional documentation
├── docker-compose.yml       # Docker services configuration
├── Dockerfile               # Application container
└── pyproject.toml          # Python dependencies and config
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🔗 Additional Resources

- [API Documentation](docs/API.md) - Detailed API reference
- [Architecture Guide](docs/ARCHITECTURE.md) - System design deep-dive
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment

## 📞 Support

For issues and questions:
- GitHub Issues: [Create an issue](<repository-url>/issues)
- Email: team@example.com

---

**Built with ❤️ for AI Safety**
