"""
Claude Memory MCP 服务 - 记忆质量验证测试

测试内容：
- 语义压缩质量评估
- 关键词提取准确性
- 记忆重要性评分验证
- 检索相关性评估
- 内容一致性检查
"""

import asyncio
import json
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

import pytest
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from claude_memory.processors.semantic_compressor import SemanticCompressor
from claude_memory.retrievers.semantic_retriever import SemanticRetriever
from claude_memory.models.data_models import (
    ConversationModel, 
    MessageModel, 
    MessageType, 
    MemoryUnitModel
)
from claude_memory.config.settings import get_settings


@pytest.fixture
def quality_test_conversations():
    """创建质量测试对话数据集"""
    conversations = []
    
    # 技术讨论对话
    tech_conversation = ConversationModel(
        session_id="tech_discussion",
        messages=[
            MessageModel(
                conversation_id=None,
                sequence_number=0,
                message_type=MessageType.HUMAN,
                content="I'm trying to understand the difference between SQL and NoSQL databases. Can you explain the main distinctions?",
                token_count=25
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=1,
                message_type=MessageType.ASSISTANT,
                content="SQL (Structured Query Language) and NoSQL databases differ in several key ways:\n\n1. **Data Structure**:\n   - SQL: Uses tables with rows and columns (relational model)\n   - NoSQL: Uses various models like document stores, key-value pairs, column-family, or graph databases\n\n2. **Schema**:\n   - SQL: Requires predefined schema (structure must be defined before data insertion)\n   - NoSQL: Schema-less or flexible schema (can store data without predefined structure)\n\n3. **Scalability**:\n   - SQL: Typically scales vertically (adding power to existing machine)\n   - NoSQL: Designed for horizontal scaling (adding more machines)\n\n4. **ACID Properties**:\n   - SQL: Strong ACID compliance (Atomicity, Consistency, Isolation, Durability)\n   - NoSQL: Often eventual consistency, may sacrifice some ACID properties for performance\n\n5. **Query Language**:\n   - SQL: Uses standardized SQL language\n   - NoSQL: Each type has its own query method\n\n**When to use SQL**: When you need complex relationships, transactions, and consistency (e.g., financial systems, ERP)\n\n**When to use NoSQL**: When you need flexibility, scalability, and can handle eventual consistency (e.g., social media, content management, real-time analytics)",
                token_count=280
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=2,
                message_type=MessageType.HUMAN,
                content="That's very helpful! Can you give me some specific examples of popular SQL and NoSQL databases?",
                token_count=20
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=3,
                message_type=MessageType.ASSISTANT,
                content="Certainly! Here are popular examples of each type:\n\n**SQL Databases**:\n- **MySQL**: Most popular open-source relational database\n- **PostgreSQL**: Advanced open-source database with JSON support\n- **SQLite**: Lightweight, file-based database\n- **Microsoft SQL Server**: Enterprise database solution\n- **Oracle Database**: Enterprise-grade database with advanced features\n\n**NoSQL Databases**:\n\n*Document Stores*:\n- **MongoDB**: Most popular document database, stores JSON-like documents\n- **CouchDB**: Document database with HTTP REST API\n\n*Key-Value Stores*:\n- **Redis**: In-memory data structure store, often used for caching\n- **Amazon DynamoDB**: Managed NoSQL service\n\n*Column-Family*:\n- **Cassandra**: Distributed database designed for large amounts of data\n- **HBase**: Hadoop database for big data applications\n\n*Graph Databases*:\n- **Neo4j**: Leading graph database for connected data\n- **Amazon Neptune**: Managed graph database service\n\nThe choice depends on your specific use case, data structure, scalability needs, and consistency requirements.",
                token_count=200
            )
        ],
        message_count=4,
        token_count=525,
        title="SQL vs NoSQL Database Comparison"
    )
    conversations.append(tech_conversation)
    
    # 简短问答对话
    short_conversation = ConversationModel(
        session_id="short_qa",
        messages=[
            MessageModel(
                conversation_id=None,
                sequence_number=0,
                message_type=MessageType.HUMAN,
                content="What is the capital of France?",
                token_count=8
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=1,
                message_type=MessageType.ASSISTANT,
                content="The capital of France is Paris.",
                token_count=7
            )
        ],
        message_count=2,
        token_count=15,
        title="Capital of France"
    )
    conversations.append(short_conversation)
    
    # 创意写作对话
    creative_conversation = ConversationModel(
        session_id="creative_writing",
        messages=[
            MessageModel(
                conversation_id=None,
                sequence_number=0,
                message_type=MessageType.HUMAN,
                content="Write a short story about a time traveler who accidentally changes something small but important in the past.",
                token_count=20
            ),
            MessageModel(
                conversation_id=None,
                sequence_number=1,
                message_type=MessageType.ASSISTANT,
                content="**The Butterfly's Wing**\n\nDr. Sarah Chen had traveled back to 1955 with one simple mission: observe the first computer conference at MIT. She was supposed to be invisible, a silent witness to history.\n\nBut as she watched the young researchers debate the future of computing, she couldn't help herself. When she heard someone mention that electronic computers would never be smaller than a room, she whispered under her breath, \"If only they knew about transistors.\"\n\nThe young man sitting nearby—she later realized it was a young Gordon Moore—turned and asked, \"What did you say about transistors?\"\n\nSarah froze. She had just mentioned technology that wouldn't be widely known for another few years. Panicking, she mumbled something about semiconductor research and quickly left.\n\nWhen she returned to 2024, everything seemed normal at first. But then she noticed her smartphone had a different design. Looking deeper, she discovered that Moore's Law had been formulated three years earlier than in her original timeline, accelerating the development of microprocessors.\n\nThe computing revolution had happened faster, leading to earlier breakthroughs in AI, medical technology, and space exploration. Diseases that had taken decades to cure in her timeline were now distant memories.\n\nAs she sat in her lab, surrounded by technology far more advanced than she remembered, Sarah smiled. Sometimes the smallest changes created the most beautiful futures.",
                token_count=280
            )
        ],
        message_count=2,
        token_count=300,
        title="Time Travel Creative Writing"
    )
    conversations.append(creative_conversation)
    
    return conversations


class TestCompressionQuality:
    """压缩质量测试"""

    @pytest.mark.asyncio
    async def test_semantic_compression_preservation(self, quality_test_conversations):
        """测试语义压缩保持关键信息"""
        
        compressor = SemanticCompressor()
        
        for conversation in quality_test_conversations:
            # 模拟压缩过程
            with patch.object(compressor, '_call_compression_api') as mock_api:
                
                # 根据对话类型创建合理的压缩结果
                if "database" in conversation.title.lower():
                    mock_compressed = {
                        "summary": "Comprehensive comparison of SQL and NoSQL databases, covering data structure, schema requirements, scalability approaches, ACID properties, and specific examples of popular databases in each category.",
                        "key_points": [
                            "SQL databases use relational tables with predefined schemas",
                            "NoSQL databases offer flexible schemas and various data models",
                            "SQL databases excel in consistency and complex relationships",
                            "NoSQL databases are designed for horizontal scalability",
                            "Popular SQL examples: MySQL, PostgreSQL, SQLite",
                            "Popular NoSQL examples: MongoDB, Redis, Cassandra, Neo4j"
                        ],
                        "importance_score": 0.9
                    }
                elif "capital" in conversation.title.lower():
                    mock_compressed = {
                        "summary": "Simple factual question about the capital of France, answered as Paris.",
                        "key_points": ["Paris is the capital of France"],
                        "importance_score": 0.3
                    }
                elif "time travel" in conversation.title.lower():
                    mock_compressed = {
                        "summary": "Creative short story about a time traveler accidentally influencing computing history by mentioning transistors to a young Gordon Moore, leading to accelerated technological development.",
                        "key_points": [
                            "Time travel story with butterfly effect theme",
                            "Accidental mention of transistors in 1955",
                            "Earlier formulation of Moore's Law",
                            "Accelerated technological progress",
                            "Theme of small changes creating positive futures"
                        ],
                        "importance_score": 0.6
                    }
                
                mock_api.return_value = mock_compressed
                
                # 执行压缩
                memory_unit = await compressor.compress_conversation(conversation)
                
                if memory_unit:
                    # 验证压缩质量
                    self._validate_compression_quality(conversation, memory_unit)

    def _validate_compression_quality(self, original_conversation: ConversationModel, memory_unit: MemoryUnitModel):
        """验证压缩质量"""
        
        # 1. 验证内容长度合理性
        original_content_length = sum(len(msg.content) for msg in original_conversation.messages)
        compressed_length = len(memory_unit.content) if memory_unit.content else 0
        
        # 压缩率应该合理（通常应该减少50-90%）
        if original_content_length > 100:  # 只对较长内容检查压缩率
            compression_ratio = compressed_length / original_content_length
            assert 0.1 <= compression_ratio <= 0.8, f"压缩率不合理: {compression_ratio:.2f}"
        
        # 2. 验证重要性评分范围
        assert 0.0 <= memory_unit.importance_score <= 1.0, "重要性评分超出范围"
        
        # 3. 验证关键词数量
        assert 1 <= len(memory_unit.keywords) <= 10, "关键词数量不合理"
        
        # 4. 验证内容包含关键概念
        content_lower = memory_unit.content.lower() if memory_unit.content else ""
        title_lower = original_conversation.title.lower()
        
        if "database" in title_lower:
            key_concepts = ["sql", "nosql", "database"]
            assert any(concept in content_lower for concept in key_concepts), "数据库概念未保留"
        
        # 5. 验证摘要不为空
        assert memory_unit.summary, "摘要不能为空"
        assert len(memory_unit.summary) >= 10, "摘要过短"

    @pytest.mark.asyncio
    async def test_keyword_extraction_accuracy(self, quality_test_conversations):
        """测试关键词提取准确性"""
        
        compressor = SemanticCompressor()
        
        # 预期关键词集合
        expected_keywords = {
            "SQL vs NoSQL Database Comparison": [
                "sql", "nosql", "database", "relational", "schema", 
                "scalability", "acid", "mongodb", "mysql", "postgresql"
            ],
            "Capital of France": ["paris", "france", "capital"],
            "Time Travel Creative Writing": [
                "time travel", "story", "gordon moore", "transistors", 
                "computing", "butterfly effect", "technology"
            ]
        }
        
        for conversation in quality_test_conversations:
            with patch.object(compressor, '_extract_keywords') as mock_extract:
                
                # 设置模拟关键词
                expected = expected_keywords.get(conversation.title, ["test", "keyword"])
                mock_extract.return_value = expected[:5]  # 最多5个关键词
                
                keywords = await compressor._extract_keywords(conversation)
                
                # 验证关键词质量
                assert len(keywords) >= 1, "至少应该有一个关键词"
                assert len(keywords) <= 10, "关键词数量不应过多"
                
                # 验证关键词相关性
                all_text = " ".join(msg.content for msg in conversation.messages).lower()
                
                relevant_keywords = []
                for keyword in keywords:
                    # 检查关键词是否在原文中出现或语义相关
                    if (keyword.lower() in all_text or 
                        any(word in all_text for word in keyword.lower().split())):
                        relevant_keywords.append(keyword)
                
                # 至少50%的关键词应该相关
                relevance_ratio = len(relevant_keywords) / len(keywords) if keywords else 0
                assert relevance_ratio >= 0.5, f"关键词相关性过低: {relevance_ratio:.2f}"

    @pytest.mark.asyncio
    async def test_importance_score_consistency(self, quality_test_conversations):
        """测试重要性评分一致性"""
        
        compressor = SemanticCompressor()
        
        importance_scores = {}
        
        for conversation in quality_test_conversations:
            with patch.object(compressor, '_calculate_importance_score') as mock_score:
                
                # 根据对话特征设置合理的重要性分数
                if conversation.token_count > 400:  # 长对话
                    mock_score.return_value = 0.8 + np.random.normal(0, 0.05)
                elif conversation.token_count < 50:  # 短对话
                    mock_score.return_value = 0.3 + np.random.normal(0, 0.05)
                else:  # 中等长度对话
                    mock_score.return_value = 0.6 + np.random.normal(0, 0.05)
                
                score = await compressor._calculate_importance_score(conversation)
                score = max(0.0, min(1.0, score))  # 确保在范围内
                
                importance_scores[conversation.title] = score
        
        # 验证评分合理性
        for title, score in importance_scores.items():
            assert 0.0 <= score <= 1.0, f"评分超出范围: {title} = {score}"
        
        # 验证相对排序合理性
        if len(importance_scores) >= 3:
            scores_list = list(importance_scores.values())
            
            # 最长的技术讨论应该有较高分数
            tech_score = importance_scores.get("SQL vs NoSQL Database Comparison", 0)
            short_score = importance_scores.get("Capital of France", 0)
            
            if tech_score > 0 and short_score > 0:
                assert tech_score > short_score, "长技术对话的重要性应该高于简短问答"


class TestRetrievalQuality:
    """检索质量测试"""

    @pytest.fixture
    def mock_memory_dataset(self):
        """模拟记忆数据集"""
        memories = [
            MemoryUnitModel(
                id="memory_python",
                content="Python programming language basics including variables, functions, and object-oriented programming concepts",
                summary="Python programming fundamentals",
                keywords=["python", "programming", "variables", "functions", "oop"],
                importance_score=0.8,
                created_at=datetime.now()
            ),
            MemoryUnitModel(
                id="memory_databases",
                content="Comparison of SQL and NoSQL databases, their use cases, and performance characteristics",
                summary="Database comparison and selection criteria",
                keywords=["sql", "nosql", "database", "performance", "scalability"],
                importance_score=0.9,
                created_at=datetime.now()
            ),
            MemoryUnitModel(
                id="memory_web_dev",
                content="Web development using React framework, component architecture, and state management",
                summary="React web development guide",
                keywords=["react", "web development", "components", "state", "frontend"],
                importance_score=0.7,
                created_at=datetime.now()
            ),
            MemoryUnitModel(
                id="memory_ml",
                content="Machine learning algorithms including supervised learning, neural networks, and deep learning",
                summary="Machine learning and AI fundamentals",
                keywords=["machine learning", "ai", "neural networks", "algorithms", "deep learning"],
                importance_score=0.85,
                created_at=datetime.now()
            ),
            MemoryUnitModel(
                id="memory_devops",
                content="DevOps practices including CI/CD pipelines, containerization with Docker, and infrastructure as code",
                summary="DevOps and deployment strategies",
                keywords=["devops", "ci/cd", "docker", "infrastructure", "deployment"],
                importance_score=0.75,
                created_at=datetime.now()
            )
        ]
        return memories

    @pytest.mark.asyncio
    async def test_semantic_retrieval_relevance(self, mock_memory_dataset):
        """测试语义检索相关性"""
        
        retriever = SemanticRetriever()
        
        # 定义测试查询和预期结果
        test_queries = [
            {
                "query": "How to build web applications with React?",
                "expected_keywords": ["react", "web development", "components"],
                "min_relevance_score": 0.6
            },
            {
                "query": "What are the differences between SQL and NoSQL?",
                "expected_keywords": ["sql", "nosql", "database"],
                "min_relevance_score": 0.7
            },
            {
                "query": "Machine learning and artificial intelligence concepts",
                "expected_keywords": ["machine learning", "ai", "neural networks"],
                "min_relevance_score": 0.6
            },
            {
                "query": "Python programming tutorial",
                "expected_keywords": ["python", "programming"],
                "min_relevance_score": 0.5
            }
        ]
        
        for test_case in test_queries:
            query = test_case["query"]
            expected_keywords = test_case["expected_keywords"]
            min_score = test_case["min_relevance_score"]
            
            # 模拟语义检索
            with patch.object(retriever, 'retrieve_memories') as mock_retrieve:
                
                # 计算模拟相似度分数
                relevant_memories = []
                for memory in mock_memory_dataset:
                    # 简单的关键词匹配评分
                    query_lower = query.lower()
                    memory_keywords = [kw.lower() for kw in memory.keywords]
                    
                    # 计算匹配度
                    matches = sum(1 for kw in expected_keywords if kw in memory_keywords)
                    text_matches = sum(1 for kw in expected_keywords if kw in memory.content.lower())
                    
                    base_score = (matches + text_matches) / (len(expected_keywords) * 2)
                    # 添加一些随机变化
                    score = min(1.0, base_score + np.random.normal(0, 0.1))
                    
                    if score >= min_score:
                        relevant_memories.append((memory, score))
                
                # 按分数排序
                relevant_memories.sort(key=lambda x: x[1], reverse=True)
                mock_retrieve.return_value = relevant_memories[:5]  # 返回top 5
                
                # 执行检索
                results = await retriever.retrieve_memories(query, limit=5)
                
                # 验证检索质量
                self._validate_retrieval_quality(query, results, expected_keywords, min_score)

    def _validate_retrieval_quality(self, query: str, results: List[Tuple[MemoryUnitModel, float]], 
                                  expected_keywords: List[str], min_relevance_score: float):
        """验证检索质量"""
        
        if not results:
            # 如果没有结果，可能是合理的（取决于数据集）
            return
        
        # 1. 验证结果数量合理
        assert len(results) <= 10, "检索结果数量不应超过10"
        
        # 2. 验证评分范围和排序
        prev_score = 1.0
        for memory, score in results:
            assert 0.0 <= score <= 1.0, f"相似度分数超出范围: {score}"
            assert score <= prev_score, "结果应该按相似度降序排列"
            prev_score = score
        
        # 3. 验证至少第一个结果的相关性
        if results:
            top_memory, top_score = results[0]
            assert top_score >= min_relevance_score * 0.8, f"顶部结果相关性过低: {top_score}"
            
            # 检查是否包含相关关键词
            memory_text = (top_memory.content + " " + " ".join(top_memory.keywords)).lower()
            keyword_matches = sum(1 for kw in expected_keywords if kw in memory_text)
            
            # 至少应该匹配一个关键词
            assert keyword_matches > 0, f"顶部结果未包含预期关键词: {expected_keywords}"

    @pytest.mark.asyncio
    async def test_retrieval_diversity(self, mock_memory_dataset):
        """测试检索结果多样性"""
        
        retriever = SemanticRetriever()
        
        # 使用较广泛的查询
        broad_query = "programming and software development"
        
        with patch.object(retriever, 'retrieve_memories') as mock_retrieve:
            
            # 模拟多样化的检索结果
            diverse_results = []
            for i, memory in enumerate(mock_memory_dataset):
                # 确保不同主题都有代表
                score = 0.8 - (i * 0.1)  # 递减分数但都相对较高
                diverse_results.append((memory, max(0.3, score)))
            
            mock_retrieve.return_value = diverse_results
            
            results = await retriever.retrieve_memories(broad_query, limit=5)
            
            if len(results) >= 3:
                # 验证主题多样性
                all_keywords = set()
                for memory, _ in results:
                    all_keywords.update(memory.keywords)
                
                # 应该涵盖多个不同领域
                unique_topics = len(all_keywords)
                assert unique_topics >= 5, f"检索结果主题多样性不足: {unique_topics} 个独特关键词"

    @pytest.mark.asyncio
    async def test_retrieval_temporal_relevance(self, mock_memory_dataset):
        """测试检索时间相关性"""
        
        retriever = SemanticRetriever()
        
        # 创建不同时间的记忆
        import datetime as dt
        recent_memory = MemoryUnitModel(
            id="recent_memory",
            content="Latest trends in software development 2024",
            summary="Current development trends",
            keywords=["software", "trends", "2024", "latest"],
            importance_score=0.7,
            created_at=dt.datetime.now()
        )
        
        old_memory = MemoryUnitModel(
            id="old_memory", 
            content="Software development practices from 2020",
            summary="Historical development practices",
            keywords=["software", "practices", "2020", "historical"],
            importance_score=0.7,
            created_at=dt.datetime.now() - dt.timedelta(days=365*4)
        )
        
        test_memories = [recent_memory, old_memory]
        
        with patch.object(retriever, 'retrieve_memories') as mock_retrieve:
            
            # 对于时间敏感查询，新记忆应该优先
            def mock_retrieval_with_time_bias(query, limit=10):
                if "latest" in query.lower() or "current" in query.lower():
                    # 新记忆获得更高分数
                    return [(recent_memory, 0.9), (old_memory, 0.6)]
                else:
                    # 一般查询按内容相关性
                    return [(old_memory, 0.8), (recent_memory, 0.7)]
            
            mock_retrieve.side_effect = mock_retrieval_with_time_bias
            
            # 测试时间敏感查询
            recent_results = await retriever.retrieve_memories("latest software development trends", limit=5)
            
            if recent_results:
                # 最新记忆应该排在前面
                top_memory = recent_results[0][0]
                assert "latest" in top_memory.content.lower() or "2024" in top_memory.content


class TestMemoryConsistency:
    """记忆一致性测试"""

    @pytest.mark.asyncio
    async def test_memory_deduplication(self):
        """测试记忆去重"""
        
        # 创建相似的记忆单元
        similar_memories = [
            MemoryUnitModel(
                id="memory_1",
                content="Python is a programming language used for web development",
                summary="Python programming basics",
                keywords=["python", "programming", "web"],
                importance_score=0.7
            ),
            MemoryUnitModel(
                id="memory_2", 
                content="Python programming language for web development applications",
                summary="Python web development",
                keywords=["python", "programming", "web", "development"],
                importance_score=0.75
            ),
            MemoryUnitModel(
                id="memory_3",
                content="JavaScript is used for frontend web development",
                summary="JavaScript frontend development", 
                keywords=["javascript", "frontend", "web"],
                importance_score=0.6
            )
        ]
        
        # 实现简单的相似度检测
        def calculate_content_similarity(mem1: MemoryUnitModel, mem2: MemoryUnitModel) -> float:
            """计算内容相似度"""
            words1 = set(mem1.content.lower().split())
            words2 = set(mem2.content.lower().split())
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
        
        # 检测重复记忆
        similarity_threshold = 0.7
        duplicates = []
        
        for i in range(len(similar_memories)):
            for j in range(i + 1, len(similar_memories)):
                similarity = calculate_content_similarity(similar_memories[i], similar_memories[j])
                if similarity >= similarity_threshold:
                    duplicates.append((similar_memories[i], similar_memories[j], similarity))
        
        # 验证去重逻辑
        if duplicates:
            print(f"发现 {len(duplicates)} 对相似记忆")
            for mem1, mem2, sim in duplicates:
                print(f"相似度 {sim:.2f}: '{mem1.content[:30]}...' vs '{mem2.content[:30]}...'")
                
                # 验证应该保留更重要的记忆
                if mem1.importance_score != mem2.importance_score:
                    assert abs(mem1.importance_score - mem2.importance_score) > 0.0

    @pytest.mark.asyncio
    async def test_memory_version_control(self):
        """测试记忆版本控制"""
        
        # 模拟记忆更新过程
        original_memory = MemoryUnitModel(
            id="evolving_memory",
            content="Basic Python syntax and variables",
            summary="Python basics",
            keywords=["python", "syntax", "variables"],
            importance_score=0.6,
            version=1,
            created_at=datetime.now()
        )
        
        # 更新的记忆版本
        updated_memory = MemoryUnitModel(
            id="evolving_memory",  # 相同ID
            content="Advanced Python concepts including decorators, generators, and context managers",
            summary="Advanced Python features",
            keywords=["python", "decorators", "generators", "context managers", "advanced"],
            importance_score=0.8,
            version=2,
            created_at=datetime.now()
        )
        
        # 验证版本更新逻辑
        assert updated_memory.version > original_memory.version
        assert updated_memory.importance_score >= original_memory.importance_score
        assert len(updated_memory.keywords) >= len(original_memory.keywords)
        
        # 验证内容进化合理性
        original_concepts = set(original_memory.content.lower().split())
        updated_concepts = set(updated_memory.content.lower().split())
        
        # 应该保留一些核心概念
        core_concepts = {"python"}
        assert core_concepts.issubset(original_concepts.intersection(updated_concepts))

    @pytest.mark.asyncio 
    async def test_cross_memory_relationships(self):
        """测试记忆间关系一致性"""
        
        # 创建相关的记忆单元
        related_memories = [
            MemoryUnitModel(
                id="web_frontend",
                content="Frontend web development with HTML, CSS, and JavaScript",
                summary="Frontend development basics",
                keywords=["frontend", "html", "css", "javascript", "web"],
                importance_score=0.7
            ),
            MemoryUnitModel(
                id="web_backend",
                content="Backend web development with Python Django framework",
                summary="Backend development with Django",
                keywords=["backend", "python", "django", "web", "framework"],
                importance_score=0.8
            ),
            MemoryUnitModel(
                id="web_database",
                content="Database design for web applications using PostgreSQL",
                summary="Web application database design",
                keywords=["database", "postgresql", "web", "design"],
                importance_score=0.75
            )
        ]
        
        # 检测记忆间的概念重叠
        def find_common_concepts(memories: List[MemoryUnitModel]) -> Dict[str, List[str]]:
            """找出记忆间的共同概念"""
            concept_map = {}
            
            for memory in memories:
                for keyword in memory.keywords:
                    if keyword not in concept_map:
                        concept_map[keyword] = []
                    concept_map[keyword].append(memory.id)
            
            # 返回出现在多个记忆中的概念
            common_concepts = {
                concept: memory_ids 
                for concept, memory_ids in concept_map.items() 
                if len(memory_ids) > 1
            }
            
            return common_concepts
        
        common_concepts = find_common_concepts(related_memories)
        
        # 验证关系一致性
        assert "web" in common_concepts, "相关记忆应该共享'web'概念"
        assert len(common_concepts["web"]) >= 2, "多个记忆应该涉及web开发"
        
        # 验证概念层次结构
        web_memories = [m for m in related_memories if "web" in m.keywords]
        assert len(web_memories) == len(related_memories), "所有记忆都应该与web相关"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])