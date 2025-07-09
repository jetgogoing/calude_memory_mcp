#!/bin/bash
# Claude Memory MCP Service - Logs Script
# 查看服务日志

set -e

# Colors
YELLOW='\033[1;33m'
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

print_message "$YELLOW" "📋 Showing logs (press Ctrl+C to exit)..."
echo

# Show logs with follow
$COMPOSE_CMD logs -f --tail=100