"""
成本追踪器
"""

from typing import Dict, Any
from datetime import datetime, timedelta


class CostTracker:
    """API成本追踪器"""
    
    # 模型成本定价（每1000 tokens）
    MODEL_COSTS = {
        # Gemini
        "gemini-2.5-flash": {"input": 0.000075, "output": 0.00015},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
        
        # OpenRouter
        "deepseek-v3": {"input": 0.001, "output": 0.002},
        "o3-mini": {"input": 0.015, "output": 0.06},
        
        # Embeddings
        "text-embedding-3-small": {"input": 0.00002, "output": 0},
        "text-embedding-004": {"input": 0.000025, "output": 0}
    }
    
    def __init__(self):
        self.session_costs = []
        self.total_cost = 0.0
        self.daily_costs = {}
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        计算成本
        
        Args:
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
            
        Returns:
            成本（美元）
        """
        if model not in self.MODEL_COSTS:
            # 使用默认成本
            input_cost = 0.001
            output_cost = 0.002
        else:
            input_cost = self.MODEL_COSTS[model]["input"]
            output_cost = self.MODEL_COSTS[model]["output"]
        
        cost = (input_tokens / 1000 * input_cost) + (output_tokens / 1000 * output_cost)
        
        # 记录成本
        self._record_cost(model, cost)
        
        return cost
    
    def _record_cost(self, model: str, cost: float) -> None:
        """记录成本"""
        now = datetime.now()
        date_key = now.strftime("%Y-%m-%d")
        
        self.session_costs.append({
            "timestamp": now,
            "model": model,
            "cost": cost
        })
        
        self.total_cost += cost
        
        if date_key not in self.daily_costs:
            self.daily_costs[date_key] = 0.0
        self.daily_costs[date_key] += cost
    
    def get_total_cost(self) -> float:
        """获取总成本"""
        return self.total_cost
    
    def get_session_cost(self) -> float:
        """获取会话成本"""
        return sum(item["cost"] for item in self.session_costs)
    
    def get_daily_estimate(self) -> float:
        """获取每日成本估算"""
        if not self.daily_costs:
            return 0.0
        
        # 取最近7天的平均值
        recent_costs = []
        now = datetime.now()
        
        for i in range(7):
            date = now - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            if date_key in self.daily_costs:
                recent_costs.append(self.daily_costs[date_key])
        
        if recent_costs:
            return sum(recent_costs) / len(recent_costs)
        
        return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_cost": self.total_cost,
            "session_cost": self.get_session_cost(),
            "daily_estimate": self.get_daily_estimate(),
            "session_count": len(self.session_costs),
            "daily_breakdown": self.daily_costs
        }