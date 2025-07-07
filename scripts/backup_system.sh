#!/bin/bash
"""
Claude Memory 自动备份脚本
"""

BACKUP_DIR="$HOME/backups"
DATE=$(date +%F)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🔄 开始Claude Memory系统备份 - $TIMESTAMP"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 1. PostgreSQL数据库备份
echo "📊 备份PostgreSQL数据库..."
PGPASSWORD=password pg_dump -h localhost -U claude_memory -d claude_memory_db \
    -Fc -f "$BACKUP_DIR/claude_memory_${DATE}.dump" 2>/dev/null && \
    echo "✅ PostgreSQL备份完成" || echo "❌ PostgreSQL备份失败"

# 2. Qdrant向量数据库备份
echo "🔍 备份Qdrant向量数据..."
if curl -s http://localhost:6333/collections/claude_memory_vectors_v14/snapshots -X POST \
    -H "Content-Type: application/json" -d '{}' > /dev/null; then
    echo "✅ Qdrant快照创建完成"
else
    echo "❌ Qdrant快照创建失败"
fi

# 3. 配置文件备份
echo "⚙️ 备份配置文件..."
tar -czf "$BACKUP_DIR/config_${DATE}.tar.gz" \
    .env config/ logs/*.log 2>/dev/null && \
    echo "✅ 配置文件备份完成" || echo "❌ 配置文件备份失败"

# 4. 清理旧备份（保留7天）
echo "🧹 清理旧备份文件..."
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +7 -delete 2>/dev/null

echo "✅ 备份完成 - $(date)"
ls -lh "$BACKUP_DIR"/*${DATE}* 2>/dev/null