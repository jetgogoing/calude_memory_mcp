#!/bin/bash
# Claude Memory MCP Service - Stop Script
# 优雅停止所有服务

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
cd "$(dirname "$0")/../.."

# Change to docker directory
DOCKER_DIR="deploy/docker"

# Detect docker-compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    print_message "$RED" "❌ Docker Compose not found!"
    exit 1
fi

print_message "$YELLOW" "🛑 Stopping Claude Memory services..."

cd $DOCKER_DIR
if $COMPOSE_CMD down; then
    print_message "$GREEN" "✅ All services stopped successfully!"
    print_message "$YELLOW" "💾 Data is preserved in Docker volumes"
else
    print_message "$RED" "❌ Failed to stop services"
    exit 1
fi