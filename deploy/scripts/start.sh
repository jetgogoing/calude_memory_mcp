#!/bin/bash
# Claude Memory MCP Service - Start Script
# 一键启动脚本 - 支持跨平台部署

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if Docker is running
check_docker() {
    print_message "$YELLOW" "🔍 Checking Docker status..."
    
    if ! command -v docker &> /dev/null; then
        print_message "$RED" "❌ Docker is not installed. Please install Docker Desktop first."
        print_message "$YELLOW" "   Visit: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        print_message "$RED" "❌ Docker is not running. Please start Docker Desktop and try again."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version > /dev/null 2>&1; then
            print_message "$RED" "❌ Docker Compose is not installed."
            exit 1
        else
            # Use docker compose instead of docker-compose
            COMPOSE_CMD="docker compose"
        fi
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    print_message "$GREEN" "✅ Docker is running"
}

# Create .env file if it doesn't exist
setup_env() {
    if [ ! -f $DOCKER_DIR/.env ]; then
        print_message "$YELLOW" "📝 Creating .env file from template..."
        if [ -f .env.minimal ]; then
            cp .env.minimal $DOCKER_DIR/.env
            print_message "$GREEN" "✅ Created .env file from minimal template."
            print_message "$YELLOW" "   Please edit $DOCKER_DIR/.env to add your API keys."
        elif [ -f .env.example ]; then
            cp .env.example $DOCKER_DIR/.env
            print_message "$GREEN" "✅ Created .env file. Please edit it to add your API keys."
        else
            print_message "$RED" "❌ No .env template found!"
            exit 1
        fi
    else
        print_message "$GREEN" "✅ Using existing .env file"
    fi
}

# Check if ports are available
check_ports() {
    print_message "$YELLOW" "🔍 Checking port availability..."
    
    local ports=("5432" "6333" "6334")
    local port_names=("PostgreSQL" "Qdrant HTTP" "Qdrant gRPC")
    local all_clear=true
    
    for i in "${!ports[@]}"; do
        port="${ports[$i]}"
        name="${port_names[$i]}"
        
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$port "; then
            print_message "$RED" "❌ Port $port ($name) is already in use!"
            print_message "$YELLOW" "   You can change the port in .env file"
            all_clear=false
        fi
    done
    
    if [ "$all_clear" = true ]; then
        print_message "$GREEN" "✅ All ports are available"
    else
        print_message "$YELLOW" "⚠️  Some ports are in use. Please check .env file to change ports."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Start services
start_services() {
    print_message "$YELLOW" "🚀 Starting Claude Memory services..."
    
    # Pull latest images
    print_message "$YELLOW" "📦 Pulling latest Docker images..."
    cd $DOCKER_DIR
    $COMPOSE_CMD pull
    
    # Start services
    if $COMPOSE_CMD up -d; then
        print_message "$GREEN" "✅ Services started successfully!"
    else
        print_message "$RED" "❌ Failed to start services"
        exit 1
    fi
    
    # Wait for services to be ready
    print_message "$YELLOW" "⏳ Waiting for services to be ready..."
    sleep 5
    
    # Check service health
    if $COMPOSE_CMD ps | grep -q "Up"; then
        print_message "$GREEN" "✅ All services are running!"
        echo
        print_message "$GREEN" "🎉 Claude Memory MCP Service is ready!"
        print_message "$YELLOW" "   PostgreSQL: localhost:5432"
        print_message "$YELLOW" "   Qdrant: http://localhost:6333"
        echo
        print_message "$YELLOW" "📊 View logs: ./deploy/scripts/logs.sh"
        print_message "$YELLOW" "🛑 Stop services: ./deploy/scripts/stop.sh"
    else
        print_message "$RED" "❌ Some services failed to start"
        print_message "$YELLOW" "Check logs with: $COMPOSE_CMD logs"
        exit 1
    fi
}

# Main execution
main() {
    print_message "$GREEN" "🧠 Claude Memory MCP Service - Startup Script"
    echo
    
    # Change to project root directory
    cd "$(dirname "$0")/../.."
    
    # Change to docker directory for compose
    DOCKER_DIR="deploy/docker"
    
    # Run checks and start
    check_docker
    setup_env
    check_ports
    start_services
}

# Run main function
main