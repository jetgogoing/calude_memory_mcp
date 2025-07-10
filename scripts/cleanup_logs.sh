#!/bin/bash
# Claude Memory 日志清理脚本
# 清理无效的日志文件，保留正在使用的文件

LOG_DIR="/home/jetgogoing/claude_memory/logs"
TIMESTAMP=$(date "+%Y-%m-%d_%H-%M-%S")

echo "=== Claude Memory 日志清理开始 ==="
echo "时间: $TIMESTAMP"
echo "目录: $LOG_DIR"
echo ""

# 需要保留的文件
KEEP_FILES=(
    "mcp_server.log"       # 当前MCP服务使用
    "monitoring.json"      # 监控脚本使用
    "alerts.log"          # 告警webhook使用
    "backup.log"          # cron备份任务使用
    "weekly_analysis.log" # cron周分析任务（虽然现在不存在，但会被创建）
    "maintenance.log"     # cron维护任务（虽然现在不存在，但会被创建）
)

# 要删除的文件列表
DELETE_FILES=(
    "api_server.log"
    "api_server_test.log"
    "cron.log"
    "debug_mcp.log"
    "echo_mcp.log"
    "hybrid_mcp.log"
    "integration_test_*.json"
    "main_api.log"
    "main_api_fixed.log"
    "mcp_manual_test.log"
    "mcp_production.log"
    "mcp_server.log.2025-07-09"
    "mcp_startup.log"
    "monitoring_mcp.log"
    "monitoring_mcp_bg.log"
    "pipeline_test_report_*.json"
    "qdrant.log"
    "qdrant_restart.log"
    "stable_mcp.log"
    "systemd_error.log"
    "working_mcp.log"
)

# 统计信息
total_size_before=$(du -sh "$LOG_DIR" | cut -f1)
deleted_count=0
deleted_size=0

echo "清理前日志目录大小: $total_size_before"
echo ""
echo "开始清理无效日志文件..."
echo ""

# 删除文件
for pattern in "${DELETE_FILES[@]}"; do
    for file in $LOG_DIR/$pattern; do
        if [ -f "$file" ]; then
            file_size=$(du -h "$file" | cut -f1)
            file_name=$(basename "$file")
            
            # 检查文件是否被进程使用
            if lsof "$file" >/dev/null 2>&1; then
                echo "⚠️  跳过 $file_name (文件正在使用中)"
            else
                rm -f "$file"
                if [ $? -eq 0 ]; then
                    echo "✅ 删除 $file_name (大小: $file_size)"
                    ((deleted_count++))
                else
                    echo "❌ 删除失败 $file_name"
                fi
            fi
        fi
    done
done

echo ""
echo "=== 清理完成 ==="
echo "删除文件数: $deleted_count"
echo ""

# 显示保留的文件
echo "保留的文件:"
for file in "${KEEP_FILES[@]}"; do
    if [ -f "$LOG_DIR/$file" ]; then
        file_size=$(du -h "$LOG_DIR/$file" | cut -f1)
        echo "  - $file (大小: $file_size)"
    fi
done

total_size_after=$(du -sh "$LOG_DIR" | cut -f1)
echo ""
echo "清理后日志目录大小: $total_size_after"