# Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- 4 CPU cores, 8GB RAM minimum
- PostgreSQL 15+ (or managed service)
- Redis 7+ with RediSearch (or managed service)

## Production Deployment

### 1. Environment Configuration

Create production `.env`:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
WORKERS=4

# Security
SECRET_KEY=<generate-strong-random-key>
CORS_ORIGINS=["https://yourdomain.com"]

# Database (use managed service in production)
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/aifw
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis (use managed service in production)
REDIS_URL=redis://redis-host:6379
REDIS_MAX_CONNECTIONS=50

# Detection
SEMANTIC_THRESHOLD=0.85
REGEX_PATTERNS_FILE=/app/config/patterns.yaml
POLICY_CONFIG_FILE=/app/config/policies.yaml

# Monitoring
ENABLE_METRICS=true
ENABLE_DETAILED_LOGGING=true
```

### 2. Database Setup

#### Option A: Managed Service (Recommended)

**AWS RDS**:
```bash
# Create PostgreSQL 15 instance
aws rds create-db-instance \
  --db-instance-identifier aifw-prod \
  --engine postgres \
  --engine-version 15.3 \
  --db-instance-class db.t3.medium \
  --allocated-storage 100 \
  --master-username aifw_user \
  --master-user-password <strong-password>

# Install pgvector extension
psql -h <rds-endpoint> -U aifw_user -d aifw \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Google Cloud SQL**:
```bash
gcloud sql instances create aifw-prod \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=us-central1

gcloud sql databases create aifw \
  --instance=aifw-prod
```

#### Option B: Self-Hosted

Use docker-compose with persistent volumes:

```yaml
postgres:
  image: pgvector/pgvector:pg15
  volumes:
    - postgres_data:/var/lib/postgresql/data
  environment:
    POSTGRES_PASSWORD: <strong-password>
  restart: always
```

### 3. Redis Setup

#### Option A: Managed Service (Recommended)

**AWS ElastiCache**:
```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id aifw-prod \
  --engine redis \
  --cache-node-type cache.t3.medium \
  --num-cache-nodes 1 \
  --engine-version 7.0
```

**Google Cloud Memorystore**:
```bash
gcloud redis instances create aifw-prod \
  --size=5 \
  --region=us-central1 \
  --redis-version=redis_7_0
```

#### Option B: Self-Hosted

```yaml
redis:
  image: redis/redis-stack:latest
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes --maxmemory 2gb
  restart: always
```

### 4. Application Deployment

#### Option A: Docker Compose

1. **Build image**:
```bash
docker build -t aifw:latest .
```

2. **Deploy**:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. **Run migrations**:
```bash
docker-compose exec api python -m alembic upgrade head
```

4. **Seed database**:
```bash
docker-compose exec api python scripts/seed_database.py
```

#### Option B: Kubernetes

**Deployment manifest**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aifw-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aifw-api
  template:
    metadata:
      labels:
        app: aifw-api
    spec:
      containers:
      - name: api
        image: aifw:latest
        ports:
        - containerPort: 8000
        - containerPort: 50051
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: aifw-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: aifw-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: aifw-api
spec:
  selector:
    app: aifw-api
  ports:
  - name: http
    port: 80
    targetPort: 8000
  - name: grpc
    port: 50051
    targetPort: 50051
  type: LoadBalancer
```

**Horizontal Pod Autoscaler**:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aifw-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aifw-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 5. Reverse Proxy (Nginx)

```nginx
upstream aifw_backend {
    least_conn;
    server api1:8000 max_fails=3 fail_timeout=30s;
    server api2:8000 max_fails=3 fail_timeout=30s;
    server api3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name aifw.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name aifw.yourdomain.com;

    ssl_certificate /etc/ssl/certs/aifw.crt;
    ssl_certificate_key /etc/ssl/private/aifw.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
    limit_req zone=api_limit burst=20 nodelay;

    location / {
        proxy_pass http://aifw_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    location /metrics {
        deny all;
        return 403;
    }
}
```

### 6. Monitoring Setup

#### Prometheus

**prometheus.yml**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'aifw-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
```

#### Grafana Dashboards

Import dashboard JSON from `config/grafana/dashboards/aifw-dashboard.json`

Key panels:
- Request rate (req/s)
- Latency percentiles (p50, p95, p99)
- Error rate
- Detection counts
- Cache hit rate
- Database connection pool

### 7. Backup Strategy

#### Database Backups

**Automated daily backups**:
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | \
  gzip > "$BACKUP_DIR/backup_$TIMESTAMP.sql.gz"

# Keep last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

**Add to crontab**:
```
0 2 * * * /path/to/backup.sh
```

#### Redis Persistence

Enable AOF (Append-Only File):
```
appendonly yes
appendfsync everysec
```

### 8. SSL/TLS Certificates

#### Let's Encrypt (Recommended)

```bash
# Install certbot
apt-get install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d aifw.yourdomain.com

# Auto-renewal (add to crontab)
0 12 * * * certbot renew --quiet
```

### 9. Logging

#### Centralized Logging (ELK Stack)

**Filebeat configuration**:
```yaml
filebeat.inputs:
- type: container
  paths:
    - '/var/lib/docker/containers/*/*.log'
  processors:
    - add_docker_metadata: ~

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "aifw-logs-%{+yyyy.MM.dd}"
```

### 10. Security Hardening

1. **Firewall Rules**:
```bash
# Allow only necessary ports
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5432/tcp  # PostgreSQL should not be exposed
ufw deny 6379/tcp  # Redis should not be exposed
ufw enable
```

2. **Secret Management**:
```bash
# Use environment variables or secret managers
export DATABASE_URL=$(aws secretsmanager get-secret-value \
  --secret-id aifw/database-url --query SecretString --output text)
```

3. **Regular Updates**:
```bash
# Update base images monthly
docker pull python:3.11-slim
docker pull pgvector/pgvector:pg15
docker pull redis/redis-stack:latest

# Rebuild application
docker build --no-cache -t aifw:latest .
```

### 11. Performance Tuning

#### Gunicorn Configuration

```python
# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
keepalive = 5
timeout = 30
graceful_timeout = 30
```

#### PostgreSQL Tuning

```sql
-- postgresql.conf
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10485kB
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
```

### 12. Disaster Recovery

**Recovery Time Objective (RTO)**: 1 hour
**Recovery Point Objective (RPO)**: 24 hours

**DR Plan**:
1. Restore database from latest backup
2. Deploy application from Docker registry
3. Update DNS to DR environment
4. Verify services health
5. Resume traffic

### 13. Health Checks

Monitor these endpoints:
- `/health` - Overall health
- `/live` - Liveness probe
- `/ready` - Readiness probe

Alert if:
- Health check fails for >2 minutes
- p95 latency >50ms
- Error rate >1%
- Database connections >80%

### 14. Cost Optimization

**AWS Cost Estimates** (monthly):
- EC2 t3.medium (2x): ~$60
- RDS db.t3.medium: ~$70
- ElastiCache cache.t3.medium: ~$50
- Data transfer: ~$20
**Total**: ~$200/month for 50K+ prompts/hour

**Optimization Tips**:
- Use spot instances for non-critical workers
- Enable caching aggressively
- Use reserved instances for predictable workloads
- Implement request batching

### 15. Rollback Procedure

```bash
# 1. Stop new deployment
kubectl rollout pause deployment/aifw-api

# 2. Rollback to previous version
kubectl rollout undo deployment/aifw-api

# 3. Verify rollback
kubectl rollout status deployment/aifw-api

# 4. Check health
curl https://aifw.yourdomain.com/health
```

## Troubleshooting

### High Latency

1. Check cache hit rate
2. Review database query performance
3. Profile embedding generation
4. Check network latency

### Memory Issues

1. Review worker count
2. Check for memory leaks
3. Monitor Redis memory usage
4. Adjust connection pool sizes

### Database Connection Exhaustion

1. Increase pool size
2. Check for long-running queries
3. Review connection timeout settings
4. Enable connection pooling at proxy level

## Support

For production issues:
- Email: ops@yourdomain.com
- Slack: #aifw-ops
- On-call: PagerDuty integration
