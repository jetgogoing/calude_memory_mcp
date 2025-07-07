"""
Token计数器工具
"""

import tiktoken


class TokenCounter:
    """Token计数器"""
    
    def __init__(self, model: str = "cl100k_base"):
        """
        初始化
        
        Args:
            model: tiktoken编码模型名称
        """
        try:
            self.encoding = tiktoken.get_encoding(model)
        except:
            # 如果tiktoken不可用，使用简单估算
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的token数
        
        Args:
            text: 要计算的文本
            
        Returns:
            token数量
        """
        if not text:
            return 0
        
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # 简单估算：平均每4个字符一个token
            return len(text) // 4 + 1