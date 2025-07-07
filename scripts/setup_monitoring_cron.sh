#!/bin/bash
#
# 设置Claude Memory监控自动任务
# 包括成本报告、容量监控、告警检查等
#

PROJECT_ROOT="/home/jetgogoing/claude_memory"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

echo "🕒 设置Claude Memory监控自动任务..."

# 创建cron作业文件
CRON_FILE="/tmp/claude_memory_cron"

cat > "$CRON_FILE" << EOF
# Claude Memory 监控自动任务
# 每小时检查容量状态
0 * * * * cd $PROJECT_ROOT && python3 $SCRIPTS_DIR/cost_capacity_monitor.py > /dev/null 2>&1

# 每日生成成本报告 (早上8点)
0 8 * * * cd $PROJECT_ROOT && python3 $SCRIPTS_DIR/cost_capacity_monitor.py && echo "\$(date): 成本报告已生成" >> $PROJECT_ROOT/logs/cron.log

# 每周生成详细分析报告 (周一早上9点)
0 9 * * 1 cd $PROJECT_ROOT && python3 $SCRIPTS_DIR/weekly_analysis.py > $PROJECT_ROOT/logs/weekly_analysis.log 2>&1

# 每月进行数据库清理 (每月1号凌晨2点)
0 2 1 * * cd $PROJECT_ROOT && python3 $SCRIPTS_DIR/db_maintenance.py > $PROJECT_ROOT/logs/maintenance.log 2>&1

# 每5分钟更新仪表板数据
*/5 * * * * cd $PROJECT_ROOT && python3 -c "from scripts.cost_capacity_monitor import CostCapacityMonitor; CostCapacityMonitor().create_dashboard_data()" > /dev/null 2>&1

# 每天备份重要数据 (凌晨3点)
0 3 * * * cd $PROJECT_ROOT && ./scripts/backup_system.sh > $PROJECT_ROOT/logs/backup.log 2>&1
EOF

# 安装cron作业
crontab -l 2>/dev/null | grep -v "Claude Memory" > /tmp/current_cron
cat "$CRON_FILE" >> /tmp/current_cron
crontab /tmp/current_cron

# 清理临时文件
rm -f "$CRON_FILE" "/tmp/current_cron"

echo "✅ 自动监控任务已设置"

# 显示当前cron作业
echo -e "\n📋 当前计划任务:"
crontab -l | grep -A10 -B2 "Claude Memory"

# 创建日志目录
mkdir -p "$PROJECT_ROOT/logs"

echo -e "\n📝 监控任务说明:"
echo "• 每小时: 容量状态检查"
echo "• 每日8点: 成本报告生成"
echo "• 每周一9点: 详细分析报告"
echo "• 每月1号2点: 数据库维护"
echo "• 每5分钟: 仪表板数据更新"
echo "• 每日3点: 数据备份"

echo -e "\n🔍 查看日志:"
echo "tail -f $PROJECT_ROOT/logs/cron.log"
echo "tail -f $PROJECT_ROOT/logs/weekly_analysis.log"
echo "tail -f $PROJECT_ROOT/logs/maintenance.log"
echo "tail -f $PROJECT_ROOT/logs/backup.log"