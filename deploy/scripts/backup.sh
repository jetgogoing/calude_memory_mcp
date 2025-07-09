#!/bin/bash
# Claude Memory MCP Service - Backup Script
# 备份数据库和向量存储

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

# Default values
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="claude_memory_backup_${TIMESTAMP}"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--dir) BACKUP_DIR="$2"; shift ;;
        -n|--name) BACKUP_NAME="$2"; shift ;;
        -h|--help) 
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -d, --dir DIR    Backup directory (default: ./backups)"
            echo "  -n, --name NAME  Backup name (default: claude_memory_backup_TIMESTAMP)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Create backup directory
mkdir -p "$BACKUP_DIR"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_PATH"

print_message "$YELLOW" "🔄 Starting backup to $BACKUP_PATH..."

# Backup PostgreSQL
print_message "$YELLOW" "📊 Backing up PostgreSQL..."
docker exec claude-memory-postgres pg_dump -U claude_memory claude_memory > "$BACKUP_PATH/postgres_dump.sql"
if [ $? -eq 0 ]; then
    print_message "$GREEN" "✅ PostgreSQL backup completed"
else
    print_message "$RED" "❌ PostgreSQL backup failed"
    exit 1
fi

# Backup Qdrant
print_message "$YELLOW" "🔍 Backing up Qdrant vector database..."
# Create Qdrant snapshot
SNAPSHOT_NAME="backup_${TIMESTAMP}"
curl -X POST "http://localhost:6333/collections/claude_memory_vectors_v14/snapshots" \
     -H "Content-Type: application/json" \
     -d "{\"snapshot_name\": \"$SNAPSHOT_NAME\"}" \
     -s -o /dev/null

if [ $? -eq 0 ]; then
    # Wait for snapshot creation
    sleep 2
    
    # Copy snapshot from container
    docker cp claude-memory-qdrant:/qdrant/storage/collections/claude_memory_vectors_v14/snapshots/${SNAPSHOT_NAME}.snapshot \
              "$BACKUP_PATH/qdrant_snapshot.snapshot"
    
    if [ $? -eq 0 ]; then
        print_message "$GREEN" "✅ Qdrant backup completed"
    else
        print_message "$RED" "❌ Failed to copy Qdrant snapshot"
        exit 1
    fi
else
    print_message "$RED" "❌ Failed to create Qdrant snapshot"
    exit 1
fi

# Backup environment configuration (without secrets)
print_message "$YELLOW" "⚙️  Backing up configuration..."
if [ -f "deploy/docker/.env" ]; then
    grep -v "_KEY=" deploy/docker/.env | grep -v "PASSWORD=" > "$BACKUP_PATH/env_config.txt"
    print_message "$GREEN" "✅ Configuration backup completed (secrets excluded)"
fi

# Create backup metadata
cat > "$BACKUP_PATH/backup_info.txt" << EOF
Backup Information
==================
Date: $(date)
Backup Name: $BACKUP_NAME
PostgreSQL Version: $(docker exec claude-memory-postgres postgres --version | head -1)
Qdrant Collection: claude_memory_vectors_v14
EOF

# Compress backup
print_message "$YELLOW" "📦 Compressing backup..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

print_message "$GREEN" "✅ Backup completed successfully!"
print_message "$YELLOW" "📍 Backup location: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
print_message "$YELLOW" "📊 Backup size: $(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" | cut -f1)"