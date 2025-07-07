#!/usr/bin/env python3
"""
Claude Memory周度分析报告
深度分析使用趋势、成本优化和性能建议
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import statistics

class WeeklyAnalyzer:
    """周度分析器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.db_path = self.project_root / "data" / "claude_memory.db"
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def get_weekly_usage_stats(self):
        """获取周度使用统计"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 最近7天的使用统计
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as request_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cost_usd) as total_cost,
                    AVG(cost_usd) as avg_cost_per_request
                FROM cost_tracking 
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            
            daily_stats = cursor.fetchall()
            
            # 模型使用分布
            cursor.execute("""
                SELECT 
                    model_name,
                    COUNT(*) as usage_count,
                    SUM(input_tokens + output_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost,
                    AVG(cost_usd) as avg_cost
                FROM cost_tracking 
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY model_name
                ORDER BY total_cost DESC
            """)
            
            model_stats = cursor.fetchall()
            
            # 获取内存搜索统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_searches,
                    COUNT(DISTINCT query) as unique_queries
                FROM (
                    SELECT content as query
                    FROM messages 
                    WHERE created_at >= datetime('now', '-7 days')
                    AND content LIKE '%search%'
                ) searches
            """)
            
            search_stats = cursor.fetchone()
            
            conn.close()
            
            return {
                "daily_stats": daily_stats,
                "model_stats": model_stats,
                "search_stats": search_stats
            }
        except Exception as e:
            print(f"获取使用统计失败: {e}")
            return {"daily_stats": [], "model_stats": [], "search_stats": (0, 0)}
    
    def analyze_trends(self, daily_stats):
        """分析使用趋势"""
        if not daily_stats:
            return {"trend": "无数据", "growth_rate": 0, "recommendations": []}
        
        # 提取成本和请求数据
        costs = [row[4] for row in daily_stats]  # total_cost
        requests = [row[1] for row in daily_stats]  # request_count
        
        trends = {}
        
        # 成本趋势
        if len(costs) >= 2:
            cost_growth = (costs[-1] - costs[0]) / max(costs[0], 0.0001) * 100
            trends["cost_growth_percent"] = cost_growth
            trends["cost_trend"] = "上升" if cost_growth > 5 else "下降" if cost_growth < -5 else "稳定"
        else:
            trends["cost_growth_percent"] = 0
            trends["cost_trend"] = "稳定"
        
        # 请求量趋势
        if len(requests) >= 2:
            request_growth = (requests[-1] - requests[0]) / max(requests[0], 1) * 100
            trends["request_growth_percent"] = request_growth
            trends["request_trend"] = "上升" if request_growth > 10 else "下降" if request_growth < -10 else "稳定"
        else:
            trends["request_growth_percent"] = 0
            trends["request_trend"] = "稳定"
        
        # 效率指标
        if costs and requests:
            avg_cost_per_request = sum(costs) / sum(requests)
            trends["avg_cost_per_request"] = avg_cost_per_request
            
            # 效率评级
            if avg_cost_per_request < 0.001:
                trends["efficiency_rating"] = "优秀"
            elif avg_cost_per_request < 0.01:
                trends["efficiency_rating"] = "良好"
            elif avg_cost_per_request < 0.1:
                trends["efficiency_rating"] = "一般"
            else:
                trends["efficiency_rating"] = "需要优化"
        
        return trends
    
    def generate_recommendations(self, stats, trends):
        """生成优化建议"""
        recommendations = []
        
        # 基于成本趋势的建议
        if trends.get("cost_growth_percent", 0) > 20:
            recommendations.append({
                "type": "cost_optimization",
                "priority": "high",
                "title": "成本快速增长警告",
                "description": f"成本增长{trends['cost_growth_percent']:.1f}%，建议优化模型使用策略",
                "actions": [
                    "审查高成本模型的使用频率",
                    "考虑使用更经济的模型替代方案",
                    "实施请求去重和缓存机制"
                ]
            })
        
        # 基于模型使用的建议
        model_stats = stats.get("model_stats", [])
        if model_stats:
            most_expensive = model_stats[0]  # 已按成本排序
            if most_expensive[3] > 10:  # total_cost > $10
                recommendations.append({
                    "type": "model_optimization",
                    "priority": "medium",
                    "title": "模型使用优化",
                    "description": f"模型{most_expensive[0]}成本较高(${most_expensive[3]:.2f})",
                    "actions": [
                        f"评估{most_expensive[0]}的必要性",
                        "考虑在适当场景使用更经济的模型",
                        "实施智能模型选择策略"
                    ]
                })
        
        # 基于效率的建议
        if trends.get("efficiency_rating") in ["一般", "需要优化"]:
            recommendations.append({
                "type": "efficiency",
                "priority": "medium",
                "title": "效率优化建议",
                "description": f"平均请求成本较高(${trends.get('avg_cost_per_request', 0):.4f})",
                "actions": [
                    "优化prompt设计以减少token使用",
                    "实施结果缓存机制",
                    "批量处理相似请求"
                ]
            })
        
        # 基于使用量的建议
        if trends.get("request_growth_percent", 0) > 50:
            recommendations.append({
                "type": "scalability",
                "priority": "high",
                "title": "扩容规划建议",
                "description": f"请求量增长{trends['request_growth_percent']:.1f}%，需要扩容规划",
                "actions": [
                    "评估当前系统容量上限",
                    "制定扩容计划和预算",
                    "优化系统性能和并发处理能力"
                ]
            })
        
        return recommendations
    
    def generate_weekly_report(self):
        """生成周度报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print("📊 生成周度分析报告...")
        
        # 收集数据
        stats = self.get_weekly_usage_stats()
        trends = self.analyze_trends(stats["daily_stats"])
        recommendations = self.generate_recommendations(stats, trends)
        
        # 计算汇总数据
        summary = self.calculate_summary(stats, trends)
        
        # 生成完整报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "period": "last_7_days",
            "summary": summary,
            "usage_stats": stats,
            "trends": trends,
            "recommendations": recommendations,
            "metadata": {
                "generated_by": "Claude Memory Weekly Analyzer",
                "version": "1.0",
                "report_type": "weekly_analysis"
            }
        }
        
        # 保存JSON报告
        json_file = self.reports_dir / f"weekly_analysis_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 生成Markdown报告
        md_file = self.reports_dir / f"weekly_analysis_{timestamp}.md"
        self.generate_markdown_report(report, md_file)
        
        print(f"✅ 周度报告已生成:")
        print(f"  📄 JSON: {json_file}")
        print(f"  📝 Markdown: {md_file}")
        
        return report
    
    def calculate_summary(self, stats, trends):
        """计算汇总数据"""
        daily_stats = stats["daily_stats"]
        
        if not daily_stats:
            return {
                "total_requests": 0,
                "total_cost": 0,
                "avg_daily_requests": 0,
                "avg_daily_cost": 0,
                "efficiency_score": 0
            }
        
        total_requests = sum(row[1] for row in daily_stats)
        total_cost = sum(row[4] for row in daily_stats)
        total_tokens = sum(row[2] + row[3] for row in daily_stats)
        
        return {
            "total_requests": total_requests,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "avg_daily_requests": total_requests / len(daily_stats),
            "avg_daily_cost": total_cost / len(daily_stats),
            "avg_tokens_per_request": total_tokens / max(total_requests, 1),
            "cost_per_1k_tokens": (total_cost / max(total_tokens, 1)) * 1000,
            "efficiency_rating": trends.get("efficiency_rating", "未知")
        }
    
    def generate_markdown_report(self, report, file_path):
        """生成Markdown格式报告"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Claude Memory 周度分析报告\n\n")
            f.write(f"**生成时间**: {report['timestamp']}\n")
            f.write(f"**分析周期**: 最近7天\n\n")
            
            # 执行摘要
            summary = report['summary']
            f.write("## 📊 执行摘要\n\n")
            f.write(f"- **总请求数**: {summary['total_requests']:,}\n")
            f.write(f"- **总成本**: ${summary['total_cost']:.4f}\n")
            f.write(f"- **总Token数**: {summary['total_tokens']:,}\n")
            f.write(f"- **平均日请求**: {summary['avg_daily_requests']:.0f}\n")
            f.write(f"- **平均日成本**: ${summary['avg_daily_cost']:.4f}\n")
            f.write(f"- **效率评级**: {summary['efficiency_rating']}\n\n")
            
            # 趋势分析
            trends = report['trends']
            f.write("## 📈 趋势分析\n\n")
            f.write(f"- **成本趋势**: {trends.get('cost_trend', '未知')} ({trends.get('cost_growth_percent', 0):+.1f}%)\n")
            f.write(f"- **请求趋势**: {trends.get('request_trend', '未知')} ({trends.get('request_growth_percent', 0):+.1f}%)\n")
            f.write(f"- **平均请求成本**: ${trends.get('avg_cost_per_request', 0):.4f}\n\n")
            
            # 模型使用分析
            model_stats = report['usage_stats']['model_stats']
            if model_stats:
                f.write("## 🤖 模型使用分析\n\n")
                for model_name, usage_count, total_tokens, total_cost, avg_cost in model_stats:
                    f.write(f"### {model_name}\n")
                    f.write(f"- 使用次数: {usage_count:,}\n")
                    f.write(f"- Token数: {total_tokens:,}\n")
                    f.write(f"- 总成本: ${total_cost:.4f}\n")
                    f.write(f"- 平均成本: ${avg_cost:.4f}\n\n")
            
            # 优化建议
            recommendations = report['recommendations']
            if recommendations:
                f.write("## 💡 优化建议\n\n")
                for i, rec in enumerate(recommendations, 1):
                    priority_emoji = "🚨" if rec['priority'] == 'high' else "⚠️" if rec['priority'] == 'medium' else "💡"
                    f.write(f"### {i}. {priority_emoji} {rec['title']}\n\n")
                    f.write(f"**优先级**: {rec['priority'].upper()}\n\n")
                    f.write(f"{rec['description']}\n\n")
                    f.write("**建议行动**:\n")
                    for action in rec['actions']:
                        f.write(f"- {action}\n")
                    f.write("\n")
            
            # 数据详情
            daily_stats = report['usage_stats']['daily_stats']
            if daily_stats:
                f.write("## 📅 每日数据详情\n\n")
                f.write("| 日期 | 请求数 | 输入Token | 输出Token | 成本 |\n")
                f.write("|------|--------|-----------|-----------|------|\n")
                for date, requests, input_tokens, output_tokens, cost, _ in daily_stats:
                    f.write(f"| {date} | {requests:,} | {input_tokens:,} | {output_tokens:,} | ${cost:.4f} |\n")
                f.write("\n")
            
            f.write("---\n")
            f.write("*报告由Claude Memory Weekly Analyzer自动生成*\n")

def main():
    """主函数"""
    analyzer = WeeklyAnalyzer()
    report = analyzer.generate_weekly_report()
    
    # 显示关键指标
    summary = report['summary']
    print(f"\n📋 本周关键指标:")
    print(f"💰 总成本: ${summary['total_cost']:.4f}")
    print(f"📊 总请求: {summary['total_requests']:,}")
    print(f"⚡ 效率评级: {summary['efficiency_rating']}")
    
    # 显示关键建议
    recommendations = report['recommendations']
    if recommendations:
        print(f"\n🎯 关键建议 ({len(recommendations)}项):")
        for rec in recommendations[:3]:  # 只显示前3个
            priority_emoji = "🚨" if rec['priority'] == 'high' else "⚠️"
            print(f"  {priority_emoji} {rec['title']}")

if __name__ == "__main__":
    main()