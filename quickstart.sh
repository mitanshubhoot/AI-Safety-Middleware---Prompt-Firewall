#!/bin/bash
# Quick start script for AI Safety Middleware

set -e

echo "🚀 AI Safety Middleware - Quick Start"
echo "===================================="
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are up
echo "🔍 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is healthy"
else
    echo "⚠️  API is starting up, please wait..."
fi

if docker-compose exec -T postgres pg_isready -U aifw_user > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "⚠️  PostgreSQL is starting up, please wait..."
fi

if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "⚠️  Redis is starting up, please wait..."
fi

echo ""
echo "🗃️  Running database migrations..."
docker-compose exec -T api python -m alembic upgrade head

echo ""
echo "🌱 Seeding database with initial data..."
docker-compose exec -T api python scripts/seed_database.py

echo ""
echo "✨ Setup complete!"
echo ""
echo "🎉 Services are running:"
echo "   - API: http://localhost:8000"
echo "   - API Docs (Swagger): http://localhost:8000/docs"
echo "   - API Docs (ReDoc): http://localhost:8000/redoc"
echo "   - Metrics: http://localhost:8000/metrics"
echo "   - RedisInsight: http://localhost:8001"
echo ""
echo "📚 Quick test:"
echo '   curl -X POST http://localhost:8000/api/v1/prompts/validate \\'
echo '     -H "Content-Type: application/json" \\'
echo '     -d "{\"prompt\": \"What is AI?\"}"'
echo ""
echo "🛑 To stop services: docker-compose down"
echo "📝 To view logs: docker-compose logs -f api"
echo ""
