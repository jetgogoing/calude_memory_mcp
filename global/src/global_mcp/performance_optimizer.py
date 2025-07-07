"""
Claude Memory MCP 性能优化工具包
包含自动扩展、负载均衡、性能监控和优化建议功能
"""

import asyncio
import time
import statistics
import psutil
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import threading
import weakref


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: float
    requests_per_second: float
    avg_response_time: float
    error_rate: float
    cache_hit_rate: float
    cpu_usage: float
    memory_usage: float
    active_connections: int
    queue_length: int


@dataclass
class OptimizationSuggestion:
    """优化建议数据类"""
    category: str  # 'connection_pool', 'cache', 'database', 'system'
    priority: str  # 'high', 'medium', 'low'
    title: str
    description: str
    action: str
    estimated_improvement: str


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.alert_thresholds = {
            "high_error_rate": 0.05,  # 5%
            "high_response_time": 1.0,  # 1秒
            "low_cache_hit_rate": 0.7,  # 70%
            "high_cpu_usage": 0.8,  # 80%
            "high_memory_usage": 0.8,  # 80%
        }
        self.alerts_enabled = True
        self.alert_callbacks: List[Callable] = []
        self.logger = logging.getLogger("performance_monitor")
        
    def add_alert_callback(self, callback: Callable[[str, PerformanceMetrics], None]):
        """添加告警回调函数"""
        self.alert_callbacks.append(callback)
    
    def record_metrics(self, metrics: PerformanceMetrics):
        """记录性能指标"""
        self.metrics_history.append(metrics)
        
        if self.alerts_enabled:
            self._check_alerts(metrics)
    
    def _check_alerts(self, metrics: PerformanceMetrics):
        """检查告警条件"""
        alerts = []
        
        if metrics.error_rate > self.alert_thresholds["high_error_rate"]:
            alerts.append(f"高错误率: {metrics.error_rate:.1%}")
        
        if metrics.avg_response_time > self.alert_thresholds["high_response_time"]:
            alerts.append(f"高响应时间: {metrics.avg_response_time:.2f}s")
        
        if metrics.cache_hit_rate < self.alert_thresholds["low_cache_hit_rate"]:
            alerts.append(f"低缓存命中率: {metrics.cache_hit_rate:.1%}")
        
        if metrics.cpu_usage > self.alert_thresholds["high_cpu_usage"]:
            alerts.append(f"高CPU使用率: {metrics.cpu_usage:.1%}")
        
        if metrics.memory_usage > self.alert_thresholds["high_memory_usage"]:
            alerts.append(f"高内存使用率: {metrics.memory_usage:.1%}")
        
        # 触发告警回调
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert, metrics)
                except Exception as e:
                    self.logger.error(f"告警回调执行失败: {e}")
    
    def get_recent_metrics(self, duration_minutes: int = 5) -> List[PerformanceMetrics]:
        """获取最近N分钟的指标"""
        cutoff_time = time.time() - (duration_minutes * 60)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_performance_summary(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """获取性能摘要"""
        recent_metrics = self.get_recent_metrics(duration_minutes)
        
        if not recent_metrics:
            return {"error": "No recent metrics available"}
        
        return {
            "timeframe_minutes": duration_minutes,
            "total_samples": len(recent_metrics),
            "avg_qps": statistics.mean(m.requests_per_second for m in recent_metrics),
            "avg_response_time": statistics.mean(m.avg_response_time for m in recent_metrics),
            "avg_error_rate": statistics.mean(m.error_rate for m in recent_metrics),
            "avg_cache_hit_rate": statistics.mean(m.cache_hit_rate for m in recent_metrics),
            "avg_cpu_usage": statistics.mean(m.cpu_usage for m in recent_metrics),
            "avg_memory_usage": statistics.mean(m.memory_usage for m in recent_metrics),
            "max_qps": max(m.requests_per_second for m in recent_metrics),
            "min_response_time": min(m.avg_response_time for m in recent_metrics),
            "max_response_time": max(m.avg_response_time for m in recent_metrics),
        }


class AutoScaler:
    """自动扩展器"""
    
    def __init__(self, min_connections: int = 5, max_connections: int = 50):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.current_connections = min_connections
        self.scale_up_threshold = 0.8  # 80%使用率触发扩展
        self.scale_down_threshold = 0.3  # 30%使用率触发缩减
        self.scale_cooldown = 60  # 60秒冷却期
        self.last_scale_time = 0
        self.logger = logging.getLogger("auto_scaler")
        
    def should_scale_up(self, metrics: PerformanceMetrics) -> bool:
        """判断是否应该扩展"""
        if time.time() - self.last_scale_time < self.scale_cooldown:
            return False
        
        if self.current_connections >= self.max_connections:
            return False
        
        # 检查多个指标
        conditions = [
            metrics.active_connections / self.current_connections > self.scale_up_threshold,
            metrics.avg_response_time > 0.5,  # 响应时间超过500ms
            metrics.queue_length > 10,  # 队列长度超过10
        ]
        
        return sum(conditions) >= 2  # 至少满足2个条件
    
    def should_scale_down(self, metrics: PerformanceMetrics) -> bool:
        """判断是否应该缩减"""
        if time.time() - self.last_scale_time < self.scale_cooldown:
            return False
        
        if self.current_connections <= self.min_connections:
            return False
        
        # 检查使用率低且性能良好
        conditions = [
            metrics.active_connections / self.current_connections < self.scale_down_threshold,
            metrics.avg_response_time < 0.1,  # 响应时间低于100ms
            metrics.queue_length < 2,  # 队列长度小于2
        ]
        
        return all(conditions)  # 必须满足所有条件
    
    def get_scale_recommendation(self, metrics: PerformanceMetrics) -> Optional[Tuple[str, int]]:
        """获取扩展建议"""
        if self.should_scale_up(metrics):
            new_size = min(self.current_connections + 2, self.max_connections)
            return "scale_up", new_size
        elif self.should_scale_down(metrics):
            new_size = max(self.current_connections - 1, self.min_connections)
            return "scale_down", new_size
        return None
    
    def apply_scaling(self, action: str, new_size: int):
        """应用扩展决策"""
        old_size = self.current_connections
        self.current_connections = new_size
        self.last_scale_time = time.time()
        
        self.logger.info(f"连接池{action}: {old_size} -> {new_size}")


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.monitor = PerformanceMonitor()
        self.auto_scaler = AutoScaler()
        self.optimization_history: List[OptimizationSuggestion] = []
        self.logger = logging.getLogger("performance_optimizer")
        
        # 注册告警回调
        self.monitor.add_alert_callback(self._handle_alert)
        
        # 性能收集任务
        self._monitoring_task = None
        self._monitoring_interval = 10  # 10秒
        self._is_running = False
    
    async def start_monitoring(self):
        """开始性能监控"""
        if self._monitoring_task is not None:
            return
        
        self._is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("性能监控已启动")
    
    async def stop_monitoring(self):
        """停止性能监控"""
        self._is_running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        self.logger.info("性能监控已停止")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self._is_running:
            try:
                metrics = await self._collect_metrics()
                self.monitor.record_metrics(metrics)
                
                # 检查自动扩展
                await self._check_auto_scaling(metrics)
                
                await asyncio.sleep(self._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(self._monitoring_interval)
    
    async def _collect_metrics(self) -> PerformanceMetrics:
        """收集当前性能指标"""
        # 获取系统指标
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        memory_usage = memory_info.percent / 100.0
        
        # 获取应用指标
        app_stats = await self.memory_manager.get_performance_stats()
        
        return PerformanceMetrics(
            timestamp=time.time(),
            requests_per_second=app_stats.get("requests_per_second", 0),
            avg_response_time=app_stats["concurrent_stats"]["avg_response_time"],
            error_rate=app_stats["concurrent_stats"]["error_count"] / max(app_stats["concurrent_stats"]["total_requests"], 1),
            cache_hit_rate=app_stats["cache_stats"]["hit_rate"],
            cpu_usage=cpu_usage / 100.0,
            memory_usage=memory_usage,
            active_connections=app_stats["connection_pool"]["total_connections"],
            queue_length=app_stats["batch_queue_size"]
        )
    
    async def _check_auto_scaling(self, metrics: PerformanceMetrics):
        """检查自动扩展"""
        recommendation = self.auto_scaler.get_scale_recommendation(metrics)
        
        if recommendation:
            action, new_size = recommendation
            self.auto_scaler.apply_scaling(action, new_size)
            
            # 这里可以通知连接池管理器调整连接数
            # await self.memory_manager.update_connection_pool_size(new_size)
    
    def _handle_alert(self, alert_msg: str, metrics: PerformanceMetrics):
        """处理告警"""
        self.logger.warning(f"性能告警: {alert_msg}")
        
        # 可以在这里实现告警通知逻辑
        # 例如发送邮件、Slack通知等
    
    def analyze_performance(self, duration_minutes: int = 30) -> Dict[str, Any]:
        """分析性能并给出优化建议"""
        summary = self.monitor.get_performance_summary(duration_minutes)
        suggestions = self._generate_optimization_suggestions(summary)
        
        return {
            "performance_summary": summary,
            "optimization_suggestions": [asdict(s) for s in suggestions],
            "auto_scaling_status": {
                "current_connections": self.auto_scaler.current_connections,
                "min_connections": self.auto_scaler.min_connections,
                "max_connections": self.auto_scaler.max_connections,
                "last_scale_time": self.auto_scaler.last_scale_time
            }
        }
    
    def _generate_optimization_suggestions(self, summary: Dict[str, Any]) -> List[OptimizationSuggestion]:
        """生成优化建议"""
        suggestions = []
        
        if "error" in summary:
            return suggestions
        
        # 响应时间优化建议
        if summary["avg_response_time"] > 0.5:
            suggestions.append(OptimizationSuggestion(
                category="database",
                priority="high",
                title="响应时间过高",
                description=f"平均响应时间 {summary['avg_response_time']:.2f}s 超过建议阈值 0.5s",
                action="考虑增加数据库连接池大小、添加索引或优化查询语句",
                estimated_improvement="30-50% 响应时间降低"
            ))
        
        # 缓存命中率优化建议
        if summary["avg_cache_hit_rate"] < 0.8:
            suggestions.append(OptimizationSuggestion(
                category="cache",
                priority="medium",
                title="缓存命中率偏低",
                description=f"缓存命中率 {summary['avg_cache_hit_rate']:.1%} 低于建议值 80%",
                action="增加缓存容量、优化缓存策略或延长缓存TTL",
                estimated_improvement="20-30% 性能提升"
            ))
        
        # CPU使用率优化建议
        if summary["avg_cpu_usage"] > 0.7:
            suggestions.append(OptimizationSuggestion(
                category="system",
                priority="high",
                title="CPU使用率过高",
                description=f"CPU使用率 {summary['avg_cpu_usage']:.1%} 超过建议值 70%",
                action="考虑增加处理器核心、优化算法或启用异步处理",
                estimated_improvement="40-60% 并发能力提升"
            ))
        
        # 内存使用率优化建议
        if summary["avg_memory_usage"] > 0.8:
            suggestions.append(OptimizationSuggestion(
                category="system",
                priority="medium",
                title="内存使用率过高",
                description=f"内存使用率 {summary['avg_memory_usage']:.1%} 超过建议值 80%",
                action="增加系统内存、优化缓存大小或启用内存压缩",
                estimated_improvement="稳定性提升，减少内存不足风险"
            ))
        
        # QPS优化建议
        if summary["avg_qps"] < 10:
            suggestions.append(OptimizationSuggestion(
                category="connection_pool",
                priority="medium",
                title="查询吞吐量偏低",
                description=f"平均QPS {summary['avg_qps']:.1f} 低于预期值",
                action="增加连接池大小、启用连接复用或优化网络配置",
                estimated_improvement="2-3x 吞吐量提升"
            ))
        
        return suggestions
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取详细性能报告"""
        analysis = self.analyze_performance(duration_minutes=60)
        recent_metrics = self.monitor.get_recent_metrics(duration_minutes=10)
        
        return {
            "report_timestamp": datetime.now().isoformat(),
            "monitoring_status": "active" if self._is_running else "inactive",
            "current_performance": analysis,
            "metrics_samples": len(recent_metrics),
            "alert_thresholds": self.monitor.alert_thresholds,
            "auto_scaling_config": {
                "min_connections": self.auto_scaler.min_connections,
                "max_connections": self.auto_scaler.max_connections,
                "scale_up_threshold": self.auto_scaler.scale_up_threshold,
                "scale_down_threshold": self.auto_scaler.scale_down_threshold,
                "scale_cooldown": self.auto_scaler.scale_cooldown
            }
        }


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self):
        self.servers = []
        self.current_index = 0
        self.health_check_interval = 30
        self.unhealthy_servers = set()
        self.logger = logging.getLogger("load_balancer")
        
    def add_server(self, server_config: Dict[str, Any]):
        """添加服务器"""
        self.servers.append({
            "config": server_config,
            "weight": server_config.get("weight", 1),
            "current_connections": 0,
            "total_requests": 0,
            "last_health_check": 0,
            "is_healthy": True
        })
        
    def get_next_server(self) -> Optional[Dict[str, Any]]:
        """获取下一个服务器（轮询策略）"""
        if not self.servers:
            return None
        
        # 过滤健康的服务器
        healthy_servers = [s for s in self.servers if s["is_healthy"]]
        if not healthy_servers:
            return None
        
        # 加权轮询
        total_weight = sum(s["weight"] for s in healthy_servers)
        if total_weight == 0:
            return healthy_servers[self.current_index % len(healthy_servers)]
        
        # 找到权重对应的服务器
        current_weight = 0
        target_weight = self.current_index % total_weight
        
        for server in healthy_servers:
            current_weight += server["weight"]
            if current_weight > target_weight:
                self.current_index += 1
                return server
        
        return healthy_servers[0]
    
    async def health_check_servers(self):
        """健康检查所有服务器"""
        for server in self.servers:
            try:
                # 这里实现具体的健康检查逻辑
                # 例如ping服务器、检查响应时间等
                is_healthy = await self._check_server_health(server)
                server["is_healthy"] = is_healthy
                server["last_health_check"] = time.time()
                
            except Exception as e:
                self.logger.error(f"健康检查失败: {e}")
                server["is_healthy"] = False
    
    async def _check_server_health(self, server: Dict[str, Any]) -> bool:
        """检查单个服务器健康状态"""
        # 简化的健康检查逻辑
        # 实际实现中可以包含更复杂的检查
        return True


# 工厂函数
def create_performance_optimizer(memory_manager) -> PerformanceOptimizer:
    """创建性能优化器实例"""
    return PerformanceOptimizer(memory_manager)