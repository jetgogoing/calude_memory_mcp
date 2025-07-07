"""
Claude记忆管理MCP服务 - 文本处理工具

提供文本清理、标准化、分词、Token计算等功能。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Set

import structlog
import tiktoken

logger = structlog.get_logger(__name__)


class TextProcessor:
    """
    文本处理器 - 提供文本清理、标准化和分析功能
    
    功能特性:
    - 文本清理和标准化
    - Token计算和限制
    - 内容质量评估
    - 语言检测和处理
    """
    
    def __init__(self):
        # 加载tiktoken编码器
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4编码器
        except Exception as e:
            logger.warning("Failed to load tiktoken encoder", error=str(e))
            self.tokenizer = None
        
        # 文本清理正则表达式
        self.cleanup_patterns = {
            # 移除多余的空白字符
            'extra_whitespace': re.compile(r'\s+'),
            # 移除特殊字符（保留基本标点）
            'special_chars': re.compile(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\'\/]'),
            # 移除重复的标点符号
            'repeated_punct': re.compile(r'([\.!?]){2,}'),
            # 移除HTML标签
            'html_tags': re.compile(r'<[^>]+>'),
            # 移除URL
            'urls': re.compile(r'https?://[^\s]+'),
            # 移除邮箱
            'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        }
        
        # 低质量内容标识符
        self.low_quality_indicators = {
            'too_short': 5,  # 太短的文本
            'too_many_repeats': 0.3,  # 重复字符/单词比例
            'too_many_numbers': 0.5,  # 数字比例
            'too_many_special': 0.3,  # 特殊字符比例
        }
        
        # 停用词集合（简化版）
        self.stopwords = {
            'en': {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
            },
            'zh': {
                '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
                '他', '她', '它', '们', '这', '那', '与', '为', '上', '下', '中', '而'
            }
        }

    async def clean_and_normalize(self, text: str) -> str:
        """
        清理和标准化文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Unicode标准化
        text = unicodedata.normalize('NFKC', text)
        
        # 应用清理规则
        for pattern_name, pattern in self.cleanup_patterns.items():
            if pattern_name == 'extra_whitespace':
                text = pattern.sub(' ', text)
            elif pattern_name == 'special_chars':
                # 保留基本标点符号
                text = pattern.sub('', text)
            elif pattern_name == 'repeated_punct':
                text = pattern.sub(r'\1', text)
            else:
                text = pattern.sub('', text)
        
        # 去除首尾空白
        text = text.strip()
        
        # 限制连续换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

    async def count_tokens(self, text: str) -> int:
        """
        计算文本的Token数量
        
        Args:
            text: 文本内容
            
        Returns:
            int: Token数量
        """
        if not text:
            return 0
        
        if self.tokenizer:
            try:
                tokens = self.tokenizer.encode(text)
                return len(tokens)
            except Exception as e:
                logger.warning("Failed to count tokens with tiktoken", error=str(e))
        
        # 备用方法：估算Token数量（1 token ≈ 4 字符）
        return len(text) // 4

    async def truncate_to_tokens(
        self, text: str, max_tokens: int, preserve_sentences: bool = True
    ) -> str:
        """
        截断文本到指定Token数量
        
        Args:
            text: 文本内容
            max_tokens: 最大Token数量
            preserve_sentences: 是否保持句子完整性
            
        Returns:
            str: 截断后的文本
        """
        if not text:
            return ""
        
        current_tokens = await self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        if preserve_sentences:
            # 按句子截断
            sentences = re.split(r'[.!?]+', text)
            result = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                test_text = result + sentence + ". "
                if await self.count_tokens(test_text) > max_tokens:
                    break
                
                result = test_text
            
            return result.strip()
        else:
            # 直接按字符截断
            estimated_chars = max_tokens * 4
            return text[:estimated_chars]

    async def is_content_meaningful(self, text: str) -> bool:
        """
        判断内容是否有意义（质量检查）
        
        Args:
            text: 文本内容
            
        Returns:
            bool: 是否有意义
        """
        if not text or not isinstance(text, str):
            return False
        
        # 长度检查
        if len(text.strip()) < self.low_quality_indicators['too_short']:
            return False
        
        clean_text = text.strip().lower()
        
        # 重复内容检查
        if self._has_too_many_repeats(clean_text):
            return False
        
        # 数字比例检查
        if self._has_too_many_numbers(clean_text):
            return False
        
        # 特殊字符比例检查
        if self._has_too_many_special_chars(clean_text):
            return False
        
        # 是否包含实际词汇
        if not self._contains_meaningful_words(clean_text):
            return False
        
        return True

    def _has_too_many_repeats(self, text: str) -> bool:
        """检查是否有太多重复内容"""
        if len(text) < 10:
            return False
        
        # 检查字符重复
        char_counts = {}
        for char in text:
            if char.isalnum():
                char_counts[char] = char_counts.get(char, 0) + 1
        
        if char_counts:
            max_char_count = max(char_counts.values())
            char_repeat_ratio = max_char_count / len(text)
            if char_repeat_ratio > self.low_quality_indicators['too_many_repeats']:
                return True
        
        # 检查单词重复
        words = text.split()
        if len(words) > 1:
            word_counts = {}
            for word in words:
                if len(word) > 2:  # 忽略很短的词
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            if word_counts:
                max_word_count = max(word_counts.values())
                word_repeat_ratio = max_word_count / len(words)
                if word_repeat_ratio > self.low_quality_indicators['too_many_repeats']:
                    return True
        
        return False

    def _has_too_many_numbers(self, text: str) -> bool:
        """检查是否有太多数字"""
        if not text:
            return False
        
        number_chars = sum(1 for char in text if char.isdigit())
        number_ratio = number_chars / len(text)
        
        return number_ratio > self.low_quality_indicators['too_many_numbers']

    def _has_too_many_special_chars(self, text: str) -> bool:
        """检查是否有太多特殊字符"""
        if not text:
            return False
        
        special_chars = sum(1 for char in text if not char.isalnum() and not char.isspace())
        special_ratio = special_chars / len(text)
        
        return special_ratio > self.low_quality_indicators['too_many_special']

    def _contains_meaningful_words(self, text: str) -> bool:
        """检查是否包含有意义的单词"""
        words = re.findall(r'\b\w+\b', text.lower())
        
        if not words:
            return False
        
        # 检查是否有长度超过2的非停用词
        meaningful_words = 0
        for word in words:
            if len(word) > 2:
                # 简单检查：不在英文停用词中
                if word not in self.stopwords.get('en', set()):
                    meaningful_words += 1
        
        # 至少要有一定比例的有意义单词
        meaningful_ratio = meaningful_words / len(words)
        return meaningful_ratio > 0.1

    async def extract_keywords(
        self, text: str, max_keywords: int = 10
    ) -> List[str]:
        """
        提取文本关键词
        
        Args:
            text: 文本内容
            max_keywords: 最大关键词数量
            
        Returns:
            List[str]: 关键词列表
        """
        if not text:
            return []
        
        # 简单的关键词提取算法
        words = re.findall(r'\b\w+\b', text.lower())
        
        # 过滤停用词和短词
        filtered_words = []
        for word in words:
            if (len(word) > 2 and 
                word not in self.stopwords.get('en', set()) and
                word not in self.stopwords.get('zh', set())):
                filtered_words.append(word)
        
        # 计算词频
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序并返回
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:max_keywords]]
        
        return keywords

    async def compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（简单版本）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            float: 相似度分数 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 提取关键词
        keywords1 = set(await self.extract_keywords(text1))
        keywords2 = set(await self.extract_keywords(text2))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # 计算Jaccard相似度
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))
        
        return intersection / union if union > 0 else 0.0

    async def split_into_chunks(
        self, text: str, max_chunk_tokens: int = 1000, overlap_tokens: int = 100
    ) -> List[str]:
        """
        将长文本分割成较小的块
        
        Args:
            text: 文本内容
            max_chunk_tokens: 每块最大Token数
            overlap_tokens: 重叠Token数
            
        Returns:
            List[str]: 文本块列表
        """
        if not text:
            return []
        
        total_tokens = await self.count_tokens(text)
        if total_tokens <= max_chunk_tokens:
            return [text]
        
        chunks = []
        
        # 按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = ""
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            para_tokens = await self.count_tokens(paragraph)
            
            # 如果当前段落太大，需要进一步分割
            if para_tokens > max_chunk_tokens:
                # 保存当前块（如果有内容）
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0
                
                # 分割大段落
                sentences = re.split(r'[.!?]+', paragraph)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    sentence_tokens = await self.count_tokens(sentence)
                    
                    if current_tokens + sentence_tokens > max_chunk_tokens:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                        current_tokens = sentence_tokens
                    else:
                        current_chunk += sentence + ". "
                        current_tokens += sentence_tokens
            
            # 正常大小的段落
            elif current_tokens + para_tokens > max_chunk_tokens:
                # 保存当前块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 开始新块（可能包含重叠）
                if overlap_tokens > 0 and chunks:
                    # 从上一块末尾获取重叠内容
                    prev_chunk = chunks[-1]
                    overlap_text = await self.truncate_to_tokens(
                        prev_chunk, overlap_tokens, preserve_sentences=True
                    )
                    current_chunk = overlap_text + "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                
                current_tokens = await self.count_tokens(current_chunk)
            else:
                # 添加到当前块
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                current_tokens += para_tokens
        
        # 添加最后一块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    async def generate_summary_prompt(self, text: str, max_length: int = 200) -> str:
        """
        生成用于摘要的提示词
        
        Args:
            text: 原始文本
            max_length: 最大摘要长度
            
        Returns:
            str: 摘要提示词
        """
        return f"""请为以下内容生成一个简洁准确的摘要，长度不超过{max_length}字符：

内容：
{text}

摘要要求：
1. 保留核心信息和关键点
2. 使用清晰简洁的语言
3. 保持原文的主要意图
4. 长度控制在{max_length}字符以内

摘要："""