# API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication. In production, implement API key-based authentication or OAuth 2.0.

## Endpoints

### Health Check

#### GET /health

Check service health status.

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "database": "healthy",
  "redis": "healthy",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Prompt Validation

#### POST /api/v1/prompts/validate

Validate a single prompt for sensitive data.

**Request Body**:
```json
{
  "prompt": "string (required)",
  "user_id": "string (optional)",
  "policy_id": "string (optional)",
  "context": {
    "department": "string (optional)",
    "custom_field": "string (optional)"
  }
}
```

**Response**: `ValidationResult`

#### POST /api/v1/prompts/validate/batch

Validate multiple prompts in parallel.

**Request Body**:
```json
{
  "prompts": [
    {
      "prompt": "string",
      "user_id": "string",
      "policy_id": "string"
    }
  ]
}
```

**Response**: `BatchValidationResult`

#### GET /api/v1/prompts/statistics

Get validation statistics.

**Response**:
```json
{
  "total_prompts": 1000,
  "total_detections": 50,
  "blocked_prompts": 25,
  "cache_hit_rate": 0.75,
  "avg_latency_ms": 15.5,
  "detections_by_type": {
    "regex": 30,
    "semantic": 20
  }
}
```

### Policy Management

#### POST /api/v1/policies

Create a new policy.

**Request Body**:
```json
{
  "name": "My Policy",
  "description": "Policy description",
  "rules": {
    "rules": [
      {
        "type": "block_pii",
        "enabled": true,
        "severity": "critical",
        "action": "block",
        "categories": ["ssn", "credit_card"]
      }
    ]
  },
  "enabled": true
}
```

#### GET /api/v1/policies/{policy_id}

Get policy by ID.

#### PUT /api/v1/policies/{policy_id}

Update existing policy.

#### DELETE /api/v1/policies/{policy_id}

Delete a policy.

#### GET /api/v1/policies

List all policies with pagination.

**Query Parameters**:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records (default: 100)

#### GET /api/v1/policies/active/list

Get all active policies.

#### POST /api/v1/policies/{policy_id}/enable

Enable a policy.

#### POST /api/v1/policies/{policy_id}/disable

Disable a policy.

## Data Models

### ValidationResult

```json
{
  "request_id": "uuid",
  "status": "allowed | blocked | warned | error",
  "is_safe": true,
  "detections": [Detection],
  "policy_id": "string",
  "latency_ms": 15.5,
  "timestamp": "2024-01-01T12:00:00Z",
  "message": "string",
  "cached": false
}
```

### Detection

```json
{
  "id": "uuid",
  "detection_type": "regex | semantic | policy | contextual",
  "matched_pattern": "string",
  "confidence_score": 0.95,
  "severity": "critical | high | medium | low | info",
  "category": "string",
  "match_positions": [[0, 10]],
  "metadata": {}
}
```

## Rate Limiting

Default: 1000 requests per minute per IP address.

Rate limit headers:
- `X-RateLimit-Limit`: Total requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time when limit resets

## Error Responses

All errors follow this format:

```json
{
  "error": "Error message",
  "details": {}
}
```

### Status Codes

- `200`: Success
- `201`: Created
- `204`: No Content
- `400`: Bad Request
- `404`: Not Found
- `429`: Too Many Requests
- `500`: Internal Server Error

## Examples with cURL

### Validate Safe Prompt

```bash
curl -X POST http://localhost:8000/api/v1/prompts/validate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is AI?"}'
```

### Validate with Unsafe Content

```bash
curl -X POST http://localhost:8000/api/v1/prompts/validate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "My SSN is 123-45-6789"}'
```

### Create Policy

```bash
curl -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Custom Policy",
    "rules": {"rules": []},
    "enabled": true
  }'
```

## Python Client Example

```python
import requests

# Validate prompt
response = requests.post(
    "http://localhost:8000/api/v1/prompts/validate",
    json={
        "prompt": "What is machine learning?",
        "user_id": "user_123"
    }
)

result = response.json()
print(f"Is safe: {result['is_safe']}")
print(f"Detections: {len(result['detections'])}")
```

## gRPC Interface

See `protos/` directory for protocol definitions.

```python
import grpc
from protos import prompt_validation_pb2, prompt_validation_pb2_grpc

channel = grpc.insecure_channel('localhost:50051')
stub = prompt_validation_pb2_grpc.PromptValidationServiceStub(channel)

request = prompt_validation_pb2.ValidatePromptRequest(
    prompt="What is AI?",
    user_id="user_123"
)

response = stub.ValidatePrompt(request)
print(f"Is safe: {response.is_safe}")
```
