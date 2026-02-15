"""Prometheus metrics for monitoring."""
from prometheus_client import Counter, Gauge, Histogram

# Request metrics
prompt_validation_total = Counter(
    "prompt_validation_total",
    "Total number of prompt validations",
    ["status", "policy"],
)

prompt_validation_duration_seconds = Histogram(
    "prompt_validation_duration_seconds",
    "Duration of prompt validation in seconds",
    ["policy"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Detection metrics
detections_by_type = Counter(
    "detections_by_type_total",
    "Total detections by type",
    ["detection_type", "severity", "blocked"],
)

regex_detections_total = Counter(
    "regex_detections_total",
    "Total regex pattern detections",
    ["pattern_name", "category"],
)

semantic_detections_total = Counter(
    "semantic_detections_total",
    "Total semantic similarity detections",
    ["confidence_bucket"],
)

policy_evaluations_total = Counter(
    "policy_evaluations_total",
    "Total policy evaluations",
    ["policy_id", "action"],
)

# Cache metrics
cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "status"],
)

cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (0-1)",
)

# Database metrics
database_operations_total = Counter(
    "database_operations_total",
    "Total database operations",
    ["operation", "table", "status"],
)

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Policy metrics
active_policies = Gauge(
    "active_policies",
    "Number of active policies",
)

# System metrics
embedding_generation_duration_seconds = Histogram(
    "embedding_generation_duration_seconds",
    "Duration of embedding generation in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

redis_vector_search_duration_seconds = Histogram(
    "redis_vector_search_duration_seconds",
    "Duration of Redis vector search in seconds",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# Error metrics
errors_total = Counter(
    "errors_total",
    "Total number of errors",
    ["error_type", "component"],
)
