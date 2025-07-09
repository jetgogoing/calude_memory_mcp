#!/bin/bash
# Claude Memory MCP Service - Restore Script
# 恢复数据库和向量存储

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

# Check arguments
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    echo "Example: $0 backups/claude_memory_backup_20240115_120000.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    print_message "$RED" "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Create temp directory for extraction
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

print_message "$YELLOW" "📦 Extracting backup..."
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find the backup directory
BACKUP_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "claude_memory_backup_*" | head -1)
if [ -z "$BACKUP_DIR" ]; then
    print_message "$RED" "❌ Invalid backup file structure"
    exit 1
fi

print_message "$GREEN" "✅ Backup extracted successfully"

# Display backup information
if [ -f "$BACKUP_DIR/backup_info.txt" ]; then
    print_message "$YELLOW" "📋 Backup Information:"
    cat "$BACKUP_DIR/backup_info.txt"
    echo
fi

# Confirm restoration
print_message "$YELLOW" "⚠️  WARNING: This will overwrite all existing data!"
read -p "Continue with restoration? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_message "$YELLOW" "❌ Restoration cancelled"
    exit 0
fi

# Check if services are running
if ! docker ps | grep -q claude-memory-postgres; then
    print_message "$RED" "❌ PostgreSQL service is not running. Please start services first."
    exit 1
fi

if ! docker ps | grep -q claude-memory-qdrant; then
    print_message "$RED" "❌ Qdrant service is not running. Please start services first."
    exit 1
fi

# Restore PostgreSQL
print_message "$YELLOW" "📊 Restoring PostgreSQL..."
if [ -f "$BACKUP_DIR/postgres_dump.sql" ]; then
    # Drop and recreate database
    docker exec claude-memory-postgres psql -U claude_memory -c "DROP DATABASE IF EXISTS claude_memory;"
    docker exec claude-memory-postgres psql -U claude_memory -c "CREATE DATABASE claude_memory;"
    
    # Restore data
    docker exec -i claude-memory-postgres psql -U claude_memory claude_memory < "$BACKUP_DIR/postgres_dump.sql"
    
    if [ $? -eq 0 ]; then
        print_message "$GREEN" "✅ PostgreSQL restored successfully"
    else
        print_message "$RED" "❌ PostgreSQL restoration failed"
        exit 1
    fi
else
    print_message "$YELLOW" "⚠️  PostgreSQL backup not found in archive"
fi

# Restore Qdrant
print_message "$YELLOW" "🔍 Restoring Qdrant vector database..."
if [ -f "$BACKUP_DIR/qdrant_snapshot.snapshot" ]; then
    # Delete existing collection
    curl -X DELETE "http://localhost:6333/collections/claude_memory_vectors_v14" -s -o /dev/null
    
    # Wait for deletion
    sleep 2
    
    # Copy snapshot to container
    SNAPSHOT_NAME="restore_$(date +%Y%m%d_%H%M%S)"
    docker cp "$BACKUP_DIR/qdrant_snapshot.snapshot" \
              claude-memory-qdrant:/qdrant/storage/collections/claude_memory_vectors_v14/snapshots/${SNAPSHOT_NAME}.snapshot
    
    # Create collection from snapshot
    curl -X PUT "http://localhost:6333/collections/claude_memory_vectors_v14/snapshots/${SNAPSHOT_NAME}/recover" \
         -H "Content-Type: application/json" \
         -s -o /dev/null
    
    if [ $? -eq 0 ]; then
        print_message "$GREEN" "✅ Qdrant restored successfully"
    else
        print_message "$RED" "❌ Qdrant restoration failed"
        exit 1
    fi
else
    print_message "$YELLOW" "⚠️  Qdrant backup not found in archive"
fi

# Display configuration info
if [ -f "$BACKUP_DIR/env_config.txt" ]; then
    print_message "$YELLOW" "⚙️  Configuration from backup (review and update .env if needed):"
    echo "---"
    cat "$BACKUP_DIR/env_config.txt"
    echo "---"
fi

print_message "$GREEN" "✅ Restoration completed successfully!"
print_message "$YELLOW" "🔄 Please restart the services to ensure everything is working properly:"
print_message "$YELLOW" "   ./deploy/scripts/stop.sh && ./deploy/scripts/start.sh"