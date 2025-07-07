"""
Claude记忆管理MCP服务 - 成本监控器

实时监控API调用成本，确保不超过预算限制。
支持多级告警和自动降级策略。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

import structlog
from pydantic import BaseModel, Field

from ..config.settings import get_settings
from ..utils.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)


class CostLevel(str, Enum):
    """成本级别"""
    NORMAL = "normal"  # 正常
    WARNING = "warning"  # 警告（80%）
    CRITICAL = "critical"  # 严重（90%）
    EXCEEDED = "exceeded"  # 超限（100%+）


class BudgetType(str, Enum):
    """预算类型"""
    DAILY = "daily"
    EMBEDDING = "embedding"
    FUSION = "fusion"
    COMPRESSION = "compression"
    TOTAL = "total"


class CostAlert(BaseModel):
    """成本告警"""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    level: CostLevel = Field(description="告警级别")
    budget_type: BudgetType = Field(description="预算类型")
    current_cost: float = Field(description="当前成本")
    budget_limit: float = Field(description="预算限制")
    usage_percent: float = Field(description="使用百分比")
    message: str = Field(description="告警消息")
    suggestions: List[str] = Field(default_factory=list, description="建议措施")


class CostReport(BaseModel):
    """成本报告"""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    daily_cost: float = Field(description="今日成本")
    daily_budget: float = Field(description="每日预算")
    daily_usage_percent: float = Field(description="每日使用率")
    
    embedding_cost: float = Field(description="嵌入成本")
    fusion_cost: float = Field(description="融合成本")
    compression_cost: float = Field(description="压缩成本")
    
    cost_by_model: Dict[str, float] = Field(default_factory=dict)
    alerts: List[CostAlert] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class CostMonitor:
    """
    成本监控器
    
    监控v1.3目标：
    - 每日成本控制在$0.3-0.5
    - 嵌入成本 < $0.2/天
    - 融合成本 < $0.1/天
    - 压缩成本 < $0.1/天
    """
    
    def __init__(
        self,
        cost_tracker: CostTracker,
        alert_callback: Optional[Callable[[CostAlert], None]] = None
    ):
        self.settings = get_settings()
        self.cost_tracker = cost_tracker
        self.alert_callback = alert_callback
        
        # 成本分类追踪
        self.cost_by_type = {
            BudgetType.EMBEDDING: 0.0,
            BudgetType.FUSION: 0.0,
            BudgetType.COMPRESSION: 0.0
        }
        
        # 告警历史
        self.alert_history: List[CostAlert] = []
        
        # 降级状态
        self.degradation_active = False
        self.degradation_level = 0
        
        logger.info(
            "cost_monitor_initialized",
            daily_budget=self.settings.cost.daily_budget_usd,
            target_cost=self.settings.cost.target_daily_cost_usd
        )
    
    def track_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_type: BudgetType
    ) -> float:
        """
        跟踪成本
        
        Args:
            model: 使用的模型
            input_tokens: 输入token数
            output_tokens: 输出token数
            cost_type: 成本类型
            
        Returns:
            计算的成本
        """
        # 计算成本
        cost = self.cost_tracker.calculate_cost(model, input_tokens, output_tokens)
        
        # 分类记录
        if cost_type in self.cost_by_type:
            self.cost_by_type[cost_type] += cost
        
        # 检查预算
        self._check_budgets()
        
        return cost
    
    def _check_budgets(self) -> None:
        """检查各项预算"""
        # 获取今日总成本
        daily_cost = self._get_today_cost()
        
        # 检查每日预算
        self._check_budget(
            BudgetType.DAILY,
            daily_cost,
            self.settings.cost.daily_budget_usd
        )
        
        # 检查嵌入预算
        self._check_budget(
            BudgetType.EMBEDDING,
            self.cost_by_type[BudgetType.EMBEDDING],
            self.settings.cost.embedding_daily_budget_usd
        )
        
        # 检查融合预算
        self._check_budget(
            BudgetType.FUSION,
            self.cost_by_type[BudgetType.FUSION],
            self.settings.cost.fusion_daily_budget_usd
        )
        
        # 检查压缩预算
        self._check_budget(
            BudgetType.COMPRESSION,
            self.cost_by_type[BudgetType.COMPRESSION],
            self.settings.cost.compression_daily_budget_usd
        )
    
    def _check_budget(
        self,
        budget_type: BudgetType,
        current_cost: float,
        budget_limit: float
    ) -> None:
        """检查单项预算"""
        usage_percent = (current_cost / budget_limit * 100) if budget_limit > 0 else 0
        
        # 确定告警级别
        if usage_percent >= 100:
            level = CostLevel.EXCEEDED
        elif usage_percent >= 90:
            level = CostLevel.CRITICAL
        elif usage_percent >= 80:
            level = CostLevel.WARNING
        else:
            level = CostLevel.NORMAL
        
        # 如果需要告警
        if level != CostLevel.NORMAL:
            alert = self._create_alert(
                level,
                budget_type,
                current_cost,
                budget_limit,
                usage_percent
            )
            
            self._handle_alert(alert)
    
    def _create_alert(
        self,
        level: CostLevel,
        budget_type: BudgetType,
        current_cost: float,
        budget_limit: float,
        usage_percent: float
    ) -> CostAlert:
        """创建告警"""
        message = f"{budget_type} 预算使用率达到 {usage_percent:.1f}%"
        
        suggestions = []
        
        if level == CostLevel.WARNING:
            suggestions.extend([
                "考虑减少API调用频率",
                "启用更多缓存策略",
                "使用更轻量的模型"
            ])
        elif level == CostLevel.CRITICAL:
            suggestions.extend([
                "立即切换到轻量模型",
                "暂停非必要的压缩操作",
                "仅保留关键功能"
            ])
        elif level == CostLevel.EXCEEDED:
            suggestions.extend([
                "启用紧急降级模式",
                "停止所有非关键API调用",
                "切换到纯嵌入模式"
            ])
        
        return CostAlert(
            level=level,
            budget_type=budget_type,
            current_cost=current_cost,
            budget_limit=budget_limit,
            usage_percent=usage_percent,
            message=message,
            suggestions=suggestions
        )
    
    def _handle_alert(self, alert: CostAlert) -> None:
        """处理告警"""
        # 记录告警
        self.alert_history.append(alert)
        
        # 日志记录
        logger.warning(
            "cost_alert",
            level=alert.level,
            budget_type=alert.budget_type,
            usage_percent=alert.usage_percent,
            message=alert.message
        )
        
        # 触发回调
        if self.alert_callback:
            self.alert_callback(alert)
        
        # 自动降级
        if self.settings.cost.auto_degradation_enabled:
            self._apply_degradation(alert)
    
    def _apply_degradation(self, alert: CostAlert) -> None:
        """应用降级策略"""
        if alert.level == CostLevel.CRITICAL:
            self.degradation_level = 1
            logger.info("cost_degradation_applied", level=1)
        elif alert.level == CostLevel.EXCEEDED:
            self.degradation_level = 2
            logger.info("cost_degradation_applied", level=2)
    
    def get_degradation_config(self) -> Dict[str, Any]:
        """
        获取降级配置
        
        Returns:
            降级配置字典
        """
        if self.degradation_level == 0:
            return {
                "fusion_enabled": True,
                "compression_enabled": True,
                "heavy_model_enabled": True
            }
        elif self.degradation_level == 1:
            return {
                "fusion_enabled": True,
                "compression_enabled": False,  # 禁用压缩
                "heavy_model_enabled": False  # 使用轻量模型
            }
        else:  # level 2
            return {
                "fusion_enabled": False,  # 禁用融合
                "compression_enabled": False,
                "heavy_model_enabled": False
            }
    
    def _get_today_cost(self) -> float:
        """获取今日成本"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.cost_tracker.daily_costs.get(today, 0.0)
    
    def generate_report(self) -> CostReport:
        """生成成本报告"""
        daily_cost = self._get_today_cost()
        daily_budget = self.settings.cost.daily_budget_usd
        
        # 获取模型成本分布
        cost_by_model = {}
        for item in self.cost_tracker.session_costs:
            model = item["model"]
            if model not in cost_by_model:
                cost_by_model[model] = 0.0
            cost_by_model[model] += item["cost"]
        
        # 生成建议
        recommendations = []
        usage_percent = (daily_cost / daily_budget * 100) if daily_budget > 0 else 0
        
        if usage_percent > 50:
            recommendations.append("成本使用已过半，建议监控使用情况")
        
        if self.cost_by_type[BudgetType.FUSION] > self.cost_by_type[BudgetType.EMBEDDING]:
            recommendations.append("融合成本较高，考虑优化融合策略")
        
        if self.degradation_level > 0:
            recommendations.append(f"当前处于降级模式（级别{self.degradation_level}）")
        
        # 获取最近的告警
        recent_alerts = [
            alert for alert in self.alert_history
            if (datetime.now() - alert.timestamp).total_seconds() < 3600
        ]
        
        return CostReport(
            daily_cost=daily_cost,
            daily_budget=daily_budget,
            daily_usage_percent=usage_percent,
            embedding_cost=self.cost_by_type[BudgetType.EMBEDDING],
            fusion_cost=self.cost_by_type[BudgetType.FUSION],
            compression_cost=self.cost_by_type[BudgetType.COMPRESSION],
            cost_by_model=cost_by_model,
            alerts=recent_alerts,
            recommendations=recommendations
        )
    
    def reset_daily_counters(self) -> None:
        """重置每日计数器"""
        self.cost_by_type = {
            BudgetType.EMBEDDING: 0.0,
            BudgetType.FUSION: 0.0,
            BudgetType.COMPRESSION: 0.0
        }
        self.degradation_level = 0
        logger.info("daily_cost_counters_reset")
    
    async def start_monitoring(self) -> None:
        """启动监控循环"""
        while True:
            try:
                # 每小时检查一次
                await asyncio.sleep(3600)
                
                # 生成报告
                report = self.generate_report()
                
                logger.info(
                    "hourly_cost_report",
                    daily_cost=report.daily_cost,
                    usage_percent=report.daily_usage_percent,
                    alerts_count=len(report.alerts)
                )
                
                # 如果是新的一天，重置计数器
                now = datetime.now()
                if now.hour == 0:
                    self.reset_daily_counters()
                    
            except Exception as e:
                logger.error("monitoring_error", error=str(e))
                await asyncio.sleep(60)  # 错误后等待1分钟