#!/usr/bin/env python3
"""
Claude Memory成本与容量监控系统
生成成本报表和容量基线监控
"""

import os
import time
import json
import psutil
import requests
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

class CostCapacityMonitor:
    """成本与容量监控器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.db_path = self.project_root / "data" / "claude_memory.db"
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # 成本配置 (每1000 tokens的成本，美元)
        self.model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gemini-2.5-pro": {"input": 0.00125, "output": 0.00375},
            "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
            "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
            "text-embedding-3-small": {"input": 0.00002, "output": 0}
        }
        
        # 容量阈值
        self.capacity_thresholds = {
            "db_size_mb": 1000,     # 数据库大小MB
            "disk_usage_percent": 80,  # 磁盘使用率%
            "memory_usage_percent": 85,  # 内存使用率%
            "cpu_usage_percent": 80,     # CPU使用率%
            "daily_requests": 10000,     # 每日请求数
            "monthly_cost_usd": 100      # 每月成本美元
        }
    
    def get_cost_data(self):
        """获取成本数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取成本统计
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    model_name,
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    SUM(cost_usd) as total_cost
                FROM cost_tracking 
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY DATE(created_at), model_name
                ORDER BY date DESC, model_name
            """)
            
            cost_data = cursor.fetchall()
            conn.close()
            
            return cost_data
        except Exception as e:
            print(f"获取成本数据失败: {e}")
            return []
    
    def get_capacity_data(self):
        """获取容量数据"""
        data = {}
        
        # 数据库大小
        if self.db_path.exists():
            data["db_size_mb"] = self.db_path.stat().st_size / (1024 * 1024)
        else:
            data["db_size_mb"] = 0
        
        # 系统资源
        data["disk_usage_percent"] = psutil.disk_usage('/').percent
        data["memory_usage_percent"] = psutil.virtual_memory().percent
        data["cpu_usage_percent"] = psutil.cpu_percent(interval=1)
        
        # 获取Prometheus指标（如果可用）
        try:
            resp = requests.get("http://localhost:8080/metrics", timeout=5)
            if resp.status_code == 200:
                metrics_text = resp.text
                
                # 解析指标
                for line in metrics_text.split('\n'):
                    if line.startswith('claude_memory_requests_total'):
                        data["total_requests"] = float(line.split()[-1])
                    elif line.startswith('claude_memory_uptime_seconds'):
                        data["uptime_seconds"] = float(line.split()[-1])
        except:
            data["total_requests"] = 0
            data["uptime_seconds"] = 0
        
        # 估算日请求量
        if data["uptime_seconds"] > 0:
            data["daily_requests"] = data["total_requests"] * (86400 / data["uptime_seconds"])
        else:
            data["daily_requests"] = 0
        
        return data
    
    def calculate_cost_analysis(self, cost_data):
        """计算成本分析"""
        analysis = {
            "daily_costs": {},
            "model_costs": {},
            "monthly_projection": 0,
            "cost_trends": []
        }
        
        total_cost = 0
        daily_totals = {}
        model_totals = {}
        
        for row in cost_data:
            date, model, input_tokens, output_tokens, cost = row
            
            # 按日期汇总
            if date not in daily_totals:
                daily_totals[date] = 0
            daily_totals[date] += cost
            
            # 按模型汇总
            if model not in model_totals:
                model_totals[model] = {"cost": 0, "tokens": 0}
            model_totals[model]["cost"] += cost
            model_totals[model]["tokens"] += input_tokens + output_tokens
            
            total_cost += cost
        
        analysis["daily_costs"] = daily_totals
        analysis["model_costs"] = model_totals
        
        # 月度投影 (基于最近7天平均)
        if len(daily_totals) > 0:
            recent_days = list(daily_totals.values())[-7:]
            avg_daily_cost = sum(recent_days) / len(recent_days)
            analysis["monthly_projection"] = avg_daily_cost * 30
        
        return analysis
    
    def check_capacity_alerts(self, capacity_data):
        """检查容量告警"""
        alerts = []
        
        for metric, threshold in self.capacity_thresholds.items():
            if metric in capacity_data:
                value = capacity_data[metric]
                
                if metric.endswith("_percent") and value > threshold:
                    alerts.append({
                        "metric": metric,
                        "value": value,
                        "threshold": threshold,
                        "severity": "warning" if value < threshold * 1.1 else "critical",
                        "message": f"{metric.replace('_', ' ').title()}: {value:.1f}% (阈值: {threshold}%)"
                    })
                elif not metric.endswith("_percent") and value > threshold:
                    alerts.append({
                        "metric": metric,
                        "value": value,
                        "threshold": threshold,
                        "severity": "warning" if value < threshold * 1.2 else "critical",
                        "message": f"{metric.replace('_', ' ').title()}: {value:.1f} (阈值: {threshold})"
                    })
        
        return alerts
    
    def generate_report(self):
        """生成成本与容量报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"cost_capacity_report_{timestamp}.json"
        
        print("📊 生成成本与容量报告...")
        
        # 收集数据
        cost_data = self.get_cost_data()
        capacity_data = self.get_capacity_data()
        cost_analysis = self.calculate_cost_analysis(cost_data)
        capacity_alerts = self.check_capacity_alerts(capacity_data)
        
        # 生成报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "period": "last_30_days",
            "cost_analysis": cost_analysis,
            "capacity_data": capacity_data,
            "capacity_alerts": capacity_alerts,
            "summary": {
                "total_cost_30d": sum(cost_analysis["daily_costs"].values()),
                "monthly_projection": cost_analysis["monthly_projection"],
                "active_alerts": len(capacity_alerts),
                "db_size_mb": capacity_data.get("db_size_mb", 0),
                "system_health": "normal" if len(capacity_alerts) == 0 else "warning"
            }
        }
        
        # 保存报告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 生成可读报告
        self.generate_readable_report(report, timestamp)
        
        print(f"✅ 报告已生成: {report_file}")
        return report
    
    def generate_readable_report(self, report, timestamp):
        """生成可读的文本报告"""
        readable_file = self.reports_dir / f"cost_capacity_summary_{timestamp}.md"
        
        with open(readable_file, 'w', encoding='utf-8') as f:
            f.write(f"# Claude Memory 成本与容量报告\n\n")
            f.write(f"**生成时间**: {report['timestamp']}\n")
            f.write(f"**报告周期**: 最近30天\n\n")
            
            # 摘要
            summary = report['summary']
            f.write("## 📊 摘要\n\n")
            f.write(f"- **30天总成本**: ${summary['total_cost_30d']:.4f}\n")
            f.write(f"- **月度成本预测**: ${summary['monthly_projection']:.4f}\n")
            f.write(f"- **数据库大小**: {summary['db_size_mb']:.1f} MB\n")
            f.write(f"- **活动告警**: {summary['active_alerts']} 个\n")
            f.write(f"- **系统健康**: {summary['system_health']}\n\n")
            
            # 成本分析
            cost_analysis = report['cost_analysis']
            f.write("## 💰 成本分析\n\n")
            
            if cost_analysis['model_costs']:
                f.write("### 按模型成本分布\n\n")
                for model, data in cost_analysis['model_costs'].items():
                    f.write(f"- **{model}**: ${data['cost']:.4f} ({data['tokens']:,} tokens)\n")
                f.write("\n")
            
            if cost_analysis['daily_costs']:
                f.write("### 最近7天成本趋势\n\n")
                recent_days = list(cost_analysis['daily_costs'].items())[-7:]
                for date, cost in recent_days:
                    f.write(f"- {date}: ${cost:.4f}\n")
                f.write("\n")
            
            # 容量状态
            capacity = report['capacity_data']
            f.write("## 🏗️ 容量状态\n\n")
            f.write(f"- **磁盘使用率**: {capacity.get('disk_usage_percent', 0):.1f}%\n")
            f.write(f"- **内存使用率**: {capacity.get('memory_usage_percent', 0):.1f}%\n")
            f.write(f"- **CPU使用率**: {capacity.get('cpu_usage_percent', 0):.1f}%\n")
            f.write(f"- **数据库大小**: {capacity.get('db_size_mb', 0):.1f} MB\n")
            f.write(f"- **预估日请求量**: {capacity.get('daily_requests', 0):.0f}\n\n")
            
            # 告警信息
            alerts = report['capacity_alerts']
            if alerts:
                f.write("## ⚠️ 容量告警\n\n")
                for alert in alerts:
                    emoji = "🚨" if alert['severity'] == 'critical' else "⚠️"
                    f.write(f"{emoji} **{alert['severity'].upper()}**: {alert['message']}\n")
                f.write("\n")
            else:
                f.write("## ✅ 容量状态正常\n\n所有指标都在正常范围内。\n\n")
            
            # 建议
            f.write("## 💡 建议\n\n")
            
            if summary['monthly_projection'] > 50:
                f.write("- 🔍 成本较高，建议优化模型使用策略\n")
            
            if capacity.get('db_size_mb', 0) > 500:
                f.write("- 🗃️ 数据库较大，考虑数据归档策略\n")
            
            if len(alerts) > 0:
                f.write("- ⚡ 存在容量告警，需要关注系统性能\n")
            
            if capacity.get('daily_requests', 0) > 5000:
                f.write("- 📈 请求量较高，考虑优化或扩容\n")
            
            f.write("\n---\n*报告由Claude Memory监控系统自动生成*\n")
        
        print(f"✅ 可读报告已生成: {readable_file}")
    
    def create_dashboard_data(self):
        """创建仪表板数据"""
        cost_data = self.get_cost_data()
        capacity_data = self.get_capacity_data()
        cost_analysis = self.calculate_cost_analysis(cost_data)
        
        dashboard_data = {
            "timestamp": time.time(),
            "metrics": {
                "cost_today": 0,
                "cost_month": cost_analysis["monthly_projection"],
                "db_size_mb": capacity_data.get("db_size_mb", 0),
                "cpu_usage": capacity_data.get("cpu_usage_percent", 0),
                "memory_usage": capacity_data.get("memory_usage_percent", 0),
                "disk_usage": capacity_data.get("disk_usage_percent", 0),
                "requests_total": capacity_data.get("total_requests", 0),
                "daily_requests": capacity_data.get("daily_requests", 0)
            },
            "alerts": self.check_capacity_alerts(capacity_data)
        }
        
        # 保存仪表板数据
        dashboard_file = self.reports_dir / "dashboard_data.json"
        with open(dashboard_file, 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        return dashboard_data

def main():
    """主函数"""
    monitor = CostCapacityMonitor()
    
    # 生成报告
    report = monitor.generate_report()
    
    # 创建仪表板数据
    dashboard_data = monitor.create_dashboard_data()
    
    # 显示摘要
    print("\n📋 报告摘要:")
    print(f"💰 30天总成本: ${report['summary']['total_cost_30d']:.4f}")
    print(f"📈 月度预测: ${report['summary']['monthly_projection']:.4f}")
    print(f"💾 数据库大小: {report['summary']['db_size_mb']:.1f} MB")
    print(f"⚠️ 活动告警: {report['summary']['active_alerts']} 个")
    
    if report['capacity_alerts']:
        print("\n🚨 容量告警:")
        for alert in report['capacity_alerts']:
            print(f"  {alert['message']}")
    
    print(f"\n📊 详细报告已保存到: reports/")

if __name__ == "__main__":
    main()