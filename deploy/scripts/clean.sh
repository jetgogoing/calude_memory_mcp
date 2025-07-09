#!/bin/bash
# Claude Memory MCP Service - Clean Script
# ⚠️ 危险操作 - 删除所有数据

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

print_message "$RED" "⚠️  WARNING: This will DELETE ALL DATA!"
print_message "$YELLOW" "This includes:"
print_message "$YELLOW" "  - All PostgreSQL data"
print_message "$YELLOW" "  - All Qdrant vectors"
print_message "$YELLOW" "  - All stored memories"
echo

read -p "Are you ABSOLUTELY sure? Type 'DELETE ALL' to confirm: " confirmation

if [ "$confirmation" = "DELETE ALL" ]; then
    print_message "$YELLOW" "🗑️  Stopping services and removing all data..."
    
    if $COMPOSE_CMD down -v; then
        print_message "$GREEN" "✅ All services stopped and data deleted!"
        print_message "$YELLOW" "💡 Run ./scripts/start.sh to start fresh"
    else
        print_message "$RED" "❌ Failed to clean up"
        exit 1
    fi
else
    print_message "$GREEN" "✅ Operation cancelled. No data was deleted."
fi