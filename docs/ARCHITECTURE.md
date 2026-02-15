# Architecture

## System Overview

The AI Safety Middleware implements a multi-layered detection pipeline with enterprise-grade observability and scalability.

## Core Components

### 1. API Layer

**FastAPI Application** (`src/main.py`)
- Async request handling with uvicorn
- CORS middleware for cross-origin requests
- Request ID tracking for distributed tracing
- Rate limiting (slowapi)
- Prometheus metrics exposure
- Health check endpoints

**Routes** (`src/api/routes/`)
- `/prompts`: Validation endpoints
- `/policies`: Policy management
- `/health`: Health checks and readiness probes

### 2. Detection Pipeline

**DetectorPipeline** (`src/core/detection/detector_pipeline.py`)

Orchestrates detection in parallel:

```
Input Prompt
     │
     ├──▶ Regex Detector ──┐
     │                     │
     ├──▶ Semantic Detector├──▶ Policy Engine ──▶ ValidationResult
     │                     │
     └──────────────────────┘
```

**Components**:

1. **RegexDetector** (`regex_detector.py`)
   - Compiled pattern matching
   - Pattern categories: api_keys, pii, passwords, etc.
   - Context-aware detection
   - O(n) complexity with early exit optimization

2. **SemanticDetector** (`semantic_detector.py`)
   - sentence-transformers for embeddings
   - Vector similarity via RediSearch
   - Cosine distance threshold (configurable)
   - Async batch processing

3. **PolicyEngine** (`policy_engine.py`)
   - YAML-based policy definitions
   - Rule evaluation engine
   - Allow/deny lists
   - Action determination (allow/block/warn)

### 3. Data Layer

**PostgreSQL Schema**:

```sql
prompts
  ├─ id (UUID, PK)
  ├─ content_hash (indexed)
  ├─ user_id (indexed)
  ├─ policy_id (indexed)
  ├─ status (indexed)
  └─ created_at (indexed)

detections
  ├─ id (UUID, PK)
  ├─ prompt_id (FK, indexed)
  ├─ detection_type (indexed)
  ├─ severity (indexed)
  └─ confidence_score

policies
  ├─ id (UUID, PK)
  ├─ policy_id (unique, indexed)
  ├─ rules (JSONB)
  └─ enabled (indexed)

audit_logs
  ├─ id (UUID, PK)
  ├─ timestamp (indexed)
  ├─ user_id (indexed)
  └─ action (indexed)
```

**Indexes**:
- B-tree indexes on frequently queried columns
- Composite indexes for common query patterns
- GiST indexes for full-text search (future)

**Redis Architecture**:

```
Redis Instance
  ├─ Cache Layer (Hash-based)
  │   └─ validation:{policy_id}:{hash} → ValidationResult
  │
  └─ Vector Store (RediSearch)
      └─ embedding:{pattern_id} → [vector, metadata]
```

### 4. Services Layer

**Service Classes**:
- `PromptService`: Validation orchestration + persistence
- `PolicyService`: Policy CRUD operations
- `AuditService`: Audit logging and retrieval

**Repository Pattern**:
- Abstract database operations
- Async SQLAlchemy 2.0
- Connection pooling
- Automatic session management

### 5. Observability

**Metrics** (Prometheus):
- Counter: `prompt_validation_total`
- Histogram: `prompt_validation_duration_seconds`
- Counter: `detections_by_type_total`
- Gauge: `cache_hit_rate`

**Logging** (structlog):
- JSON-formatted in production
- Colored console in development
- Request correlation IDs
- Performance timings

**Audit Trail**:
- Every validation logged
- User attribution
- IP address tracking
- Retention: 90 days

## Data Flow

### Validation Request Flow

```
1. Client Request
   └─▶ FastAPI Endpoint

2. Middleware Pipeline
   ├─▶ Request ID injection
   ├─▶ Rate limiting check
   └─▶ Logging

3. Service Layer
   └─▶ PromptService.validate_prompt()

4. Detection Pipeline
   ├─▶ Cache check (Redis)
   ├─▶ Parallel detection
   │   ├─ Regex patterns
   │   └─ Semantic search
   ├─▶ Policy evaluation
   └─▶ Result aggregation

5. Persistence
   ├─▶ Store prompt record
   ├─▶ Store detections
   ├─▶ Cache result
   └─▶ Audit log

6. Response
   └─▶ ValidationResult JSON
```

## Scalability Considerations

### Horizontal Scaling

- **Stateless API**: No in-memory session state
- **Database pooling**: Multiple workers share connection pool
- **Redis cluster**: Shard cache and vectors across nodes
- **Load balancing**: Round-robin or least-connections

### Vertical Scaling

- **CPU-bound**: Regex compilation, embedding generation
- **Memory-bound**: Vector storage, model loading
- **Recommended**: 4 CPU cores, 8GB RAM minimum

### Caching Strategy

1. **L1 Cache** (Redis): Validated prompts
   - TTL: 1 hour
   - Eviction: LRU
   - Hit rate target: >70%

2. **L2 Cache** (Application): Compiled patterns
   - In-memory
   - Reload on config change

### Database Optimization

- **Read replicas**: Route analytics queries
- **Connection pooling**: 20 connections per worker
- **Prepared statements**: All queries parameterized
- **Batch inserts**: For detection records

## Security Architecture

### Defense in Depth

1. **Input Validation**: Pydantic models
2. **SQL Injection Prevention**: Parameterized queries
3. **Rate Limiting**: Per-IP and per-user
4. **Audit Logging**: All actions tracked
5. **Secret Management**: Environment variables

### Threat Model

**Threats Mitigated**:
- Data exfiltration via prompts
- Credential leakage
- PII disclosure
- API key exposure

**Threats Out of Scope**:
- DDoS protection (use Cloudflare/AWS Shield)
- Application-level attacks (WAF recommended)
- Social engineering

## Performance Characteristics

### Latency Targets

- **P50**: <10ms
- **P95**: <25ms
- **P99**: <50ms

### Throughput

- **Single worker**: 50-100 req/s
- **4 workers**: 200-400 req/s
- **With caching**: 500-1000 req/s

### Resource Usage

- **Memory**: ~500MB base + 100MB per worker
- **CPU**: ~10-20% idle, ~80% under load
- **Disk**: Minimal (logs only)
- **Network**: <1MB/s typical

## Deployment Patterns

### Development

```
docker-compose up
```

### Staging

- Multiple API replicas
- Shared PostgreSQL (with replication)
- Redis Sentinel for HA

### Production

- Kubernetes deployment
- Horizontal Pod Autoscaler (HPA)
- PostgreSQL managed service (RDS/Cloud SQL)
- Redis managed service (ElastiCache/MemoryStore)
- Ingress with TLS termination

## Monitoring & Alerting

### Key Metrics

1. **Latency**: p95 > 50ms → Alert
2. **Error rate**: >1% → Alert
3. **Cache hit rate**: <50% → Warning
4. **Database connections**: >80% pool → Warning

### Dashboard Panels

- Request rate (req/s)
- Latency histogram
- Detection counts by type
- Cache performance
- Database query duration
- Error rates

## Future Enhancements

### Planned Features

1. **Streaming API**: WebSocket support for real-time validation
2. **Model fine-tuning**: Company-specific embeddings
3. **Multi-tenancy**: Isolated policies per organization
4. **A/B testing**: Policy version comparison
5. **ML model**: Train custom classifier on historical data

### Technical Debt

- gRPC service implementation (protobuf ready)
- Comprehensive test suite (>80% coverage target)
- Performance profiling and optimization
- Documentation for all modules
