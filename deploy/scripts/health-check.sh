#!/bin/bash
# Claude Memory MCP Service - Health Check Script
# 服务健康状态检查

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Change to project root
cd "$(dirname "$0")/.."

# Detect docker-compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    print_message "$RED" "❌ Docker Compose not found!"
    exit 1
fi

print_message "$YELLOW" "🏥 Checking service health status..."
echo

# Check if services are running
if ! $COMPOSE_CMD ps | grep -q "Up"; then
    print_message "$RED" "❌ Services are not running!"
    print_message "$YELLOW" "   Run ./scripts/start.sh to start services"
    exit 1
fi

# Check PostgreSQL
print_message "$YELLOW" "🐘 Checking PostgreSQL..."
if docker exec claude-memory-postgres pg_isready -U claude_memory > /dev/null 2>&1; then
    print_message "$GREEN" "✅ PostgreSQL is healthy"
    
    # Check database connection
    if docker exec claude-memory-postgres psql -U claude_memory -d claude_memory -c "SELECT 1" > /dev/null 2>&1; then
        print_message "$GREEN" "✅ Database connection successful"
    else
        print_message "$RED" "❌ Cannot connect to database"
    fi
else
    print_message "$RED" "❌ PostgreSQL is not responding"
fi

# Check Qdrant
print_message "$YELLOW" "🔷 Checking Qdrant..."
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    print_message "$GREEN" "✅ Qdrant HTTP API is healthy"
    
    # Get Qdrant info
    QDRANT_INFO=$(curl -s http://localhost:6333/collections | jq -r '.result.collections | length' 2>/dev/null || echo "0")
    print_message "$GREEN" "   Collections: $QDRANT_INFO"
else
    print_message "$RED" "❌ Qdrant is not responding"
fi

# Check Docker volumes
print_message "$YELLOW" "💾 Checking Docker volumes..."
POSTGRES_VOL=$(docker volume inspect claude-memory-postgres-data 2>/dev/null | jq -r '.[0].Name' || echo "not found")
QDRANT_VOL=$(docker volume inspect claude-memory-qdrant-data 2>/dev/null | jq -r '.[0].Name' || echo "not found")

if [ "$POSTGRES_VOL" = "claude-memory-postgres-data" ]; then
    print_message "$GREEN" "✅ PostgreSQL volume exists"
else
    print_message "$RED" "❌ PostgreSQL volume not found"
fi

if [ "$QDRANT_VOL" = "claude-memory-qdrant-data" ]; then
    print_message "$GREEN" "✅ Qdrant volume exists"
else
    print_message "$RED" "❌ Qdrant volume not found"
fi

# Summary
echo
print_message "$GREEN" "📊 Health Check Summary"
$COMPOSE_CMD ps