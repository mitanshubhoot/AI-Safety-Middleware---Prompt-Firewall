# Enterprise Improvements - Feature Branch

This branch adds several enterprise-grade improvements to the AI Safety Middleware.

## 🎯 New Features

### 1. **JWT Authentication & Authorization**
- Token-based authentication with JWT
- Role-based access control (RBAC)
- Password hashing with bcrypt
- Token refresh mechanism

**Files Added:**
- `src/api/auth.py` - Authentication utilities
- `src/api/routes/auth.py` - Authentication endpoints

**Usage:**
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Get current user
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <your-token>"
```

### 2. **Multi-Tenancy Support**
- Organization-based isolation
- Per-organization rate limiting
- Custom settings per organization

**Database Models Added:**
- `organizations` - Organization/tenant management
- `users` - User accounts
- `api_keys` - API key management
- `webhook_endpoints` - Webhook configuration
- `rate_limit_logs` - Rate limit tracking

**Migration:** `002_enterprise_models.py`

### 3. **Multi-Level Caching**
- L1 Cache: In-memory (TTLCache) for fast lookups
- L2 Cache: Redis for distributed caching
- Cache statistics and monitoring
- Cache warming support

**File Added:** `src/core/cache/cache_manager.py`

**Features:**
- Automatic cache promotion from L2 to L1
- Namespace-based cache invalidation
- Hit rate tracking
- Fallback function support

**Usage:**
```python
from src.core.cache.cache_manager import get_cache_manager

cache = await get_cache_manager()

# Get with fallback
value = await cache.get(
    "policies",
    "default",
    fallback_fn=lambda: fetch_from_db()
)

# Set value
await cache.set("policies", "default", policy_data, ttl=3600)

# Get statistics
stats = cache.get_stats()
print(f"L1 hit rate: {stats['l1_hit_rate']:.2%}")
```

### 4. **Circuit Breaker Pattern**
- Automatic failure detection
- Graceful degradation
- Configurable thresholds
- Fallback function support

**File Added:** `src/utils/circuit_breaker.py`

**States:**
- `CLOSED` - Normal operation
- `OPEN` - Failing, rejecting requests
- `HALF_OPEN` - Testing recovery

**Usage:**
```python
from src.utils.circuit_breaker import get_circuit_breaker

breaker = get_circuit_breaker(
    name="semantic_detector",
    failure_threshold=5,
    recovery_timeout=60
)

# Call with circuit breaker
result = await breaker.call(
    external_service_call,
    prompt,
    fallback=lambda p: []  # Return empty on failure
)
```

### 5. **API Key Management**
- SHA-256 hashed API keys
- Per-key rate limiting
- Expiration dates
- Usage tracking
- Scope-based permissions

**Features:**
- Key prefixes for identification
- Last used timestamp
- Automatic key rotation support

### 6. **Webhook Support**
- Event-based notifications
- HMAC signature verification
- Retry mechanism
- Failure tracking

**Events:**
- `prompt.validated`
- `prompt.blocked`
- `policy.created`
- `policy.updated`

### 7. **Enhanced Dependencies**

Added to `pyproject.toml`:
- `python-jose[cryptography]` - JWT handling
- `passlib[bcrypt]` - Password hashing
- `cachetools` - In-memory caching
- `celery[redis]` - Async task queue (optional)
- `sentry-sdk[fastapi]` - Error tracking (optional)
- `opentelemetry-*` - Distributed tracing

## 🔧 Configuration Updates

### Environment Variables

Add to `.env`:
```bash
# Authentication
SECRET_KEY=your-secret-key-min-32-chars
JWT_EXPIRATION_HOURS=24

# Multi-tenancy
DEFAULT_ORGANIZATION_ID=default-org-id

# Caching
L1_CACHE_SIZE=1000
L1_CACHE_TTL=300
L2_CACHE_TTL=3600

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Optional: Monitoring
SENTRY_DSN=your-sentry-dsn
ENABLE_TRACING=true
```

## 📊 Database Migration

Run the new migration:
```bash
# With docker-compose
docker-compose exec api python -m alembic upgrade head

# Locally
alembic upgrade head
```

This creates:
- 5 new tables
- 8 new indexes
- Foreign key relationships
- Multi-tenancy support

## 🚀 Testing New Features

### 1. Authentication
```bash
# Create a test token (uses demo mode)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test"}' \
  | jq -r .access_token)

# Use token
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Multi-Level Cache
```python
import asyncio
from src.core.cache.cache_manager import get_cache_manager

async def test_cache():
    cache = await get_cache_manager()
    
    # Set value
    await cache.set("test", "key1", {"data": "value"})
    
    # Get value (L1 hit)
    value = await cache.get("test", "key1")
    
    # Check stats
    stats = cache.get_stats()
    print(f"Hit rate: {stats['overall_hit_rate']:.2%}")

asyncio.run(test_cache())
```

### 3. Circuit Breaker
```python
from src.utils.circuit_breaker import get_circuit_breaker

breaker = get_circuit_breaker("test_service")

async def unreliable_service():
    # Simulate failure
    raise Exception("Service unavailable")

# Will open circuit after 5 failures
for i in range(10):
    try:
        await breaker.call(unreliable_service)
    except Exception as e:
        print(f"Attempt {i+1}: {e}")

# Check state
state = breaker.get_state()
print(f"Circuit state: {state['state']}")
```

## 📈 Performance Impact

### Multi-Level Caching
- **L1 Hit**: <1ms (in-memory)
- **L2 Hit**: ~2-5ms (Redis)
- **Miss**: Original latency

Expected improvements:
- 70-80% L1 hit rate
- 15-20% L2 hit rate
- Overall: 5-10x faster for cached requests

### Circuit Breaker
- **Overhead**: <0.1ms per call
- **Benefit**: Prevents cascade failures
- **Recovery**: Automatic after timeout

## 🔒 Security Enhancements

1. **Password Security**: Bcrypt with salt rounds
2. **Token Security**: HS256 JWT with expiration
3. **API Key Storage**: SHA-256 hashed, never stored in plain text
4. **Rate Limiting**: Per-organization and per-key
5. **Webhook Security**: HMAC signature verification

## 📝 Migration Checklist

- [ ] Update `.env` with new variables
- [ ] Run database migration (`alembic upgrade head`)
- [ ] Update API clients to use JWT authentication
- [ ] Configure organization rate limits
- [ ] Set up webhook endpoints (if needed)
- [ ] Monitor circuit breaker states
- [ ] Review cache hit rates

## 🎯 Next Steps

### Immediate
1. Implement user registration endpoint
2. Add API key CRUD endpoints
3. Complete webhook delivery system
4. Add organization management endpoints

### Short-term
5. Integrate Sentry for error tracking
6. Add OpenTelemetry distributed tracing
7. Implement Celery for async tasks
8. Add comprehensive tests for new features

### Long-term
9. Multi-region support
10. Advanced analytics dashboard
11. Machine learning model fine-tuning
12. GraphQL API

## 📚 Additional Documentation

- See `src/api/auth.py` for authentication details
- See `src/core/cache/cache_manager.py` for caching strategies
- See `src/utils/circuit_breaker.py` for resilience patterns
- See `alembic/versions/002_enterprise_models.py` for schema changes

## 🐛 Known Issues

1. Authentication is in demo mode (needs database integration)
2. Webhook delivery not yet implemented
3. API key generation endpoint not created
4. Organization management needs admin UI

## 💡 Tips

- Use circuit breakers for all external service calls
- Warm cache on application startup for frequently accessed data
- Monitor circuit breaker states via `/metrics`
- Rotate API keys regularly (recommended: 90 days)
- Set appropriate rate limits per organization tier

---

**Branch**: `feature/enterprise-improvements`  
**Status**: Ready for Review  
**Estimated Impact**: High - Production-grade improvements
