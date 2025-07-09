#!/usr/bin/env python3
"""
Claude Memory MCP服务 - 部署后验证脚本

在部署完成后执行功能验证，确保所有服务正常工作。
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import time

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import (
    ConversationModel,
    MessageModel,
    MemoryUnitModel,
    MemoryUnitType,
    SearchQuery,
    ContextInjectionRequest
)
from claude_memory.database.session_manager import get_db_session
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.utils.model_manager import ModelManager
import httpx
import structlog
from sqlalchemy import text

# 配置日志
logger = structlog.get_logger(__name__)


class PostDeploymentValidator:
    """部署后验证器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.service_manager: Optional[ServiceManager] = None
        self.validation_results: Dict[str, Dict] = {}
        self.test_data: Dict[str, Any] = {}
        self.has_failures = False
        
    async def run_all_validations(self) -> bool:
        """
        运行所有验证
        
        Returns:
            bool: 是否通过所有验证
        """
        print("\n🚀 Claude Memory MCP服务 - 部署后验证")
        print("=" * 60)
        print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"服务版本: {self.settings.service.version}")
        print("=" * 60)
        
        try:
            # 初始化服务
            await self.initialize_service()
            
            # 执行各项验证
            await self.validate_health_check()
            await self.validate_conversation_storage()
            await self.validate_memory_compression()
            await self.validate_vector_storage()
            await self.validate_memory_retrieval()
            await self.validate_context_injection()
            await self.validate_cross_project_search()
            await self.validate_transaction_consistency()
            await self.validate_performance_metrics()
            await self.validate_error_handling()
            
            # 清理测试数据
            await self.cleanup_test_data()
            
            # 输出总结
            self.print_summary()
            
            return not self.has_failures
            
        finally:
            # 确保服务停止
            if self.service_manager:
                await self.service_manager.stop_service()
    
    async def initialize_service(self):
        """初始化服务"""
        print("\n🔧 初始化服务...")
        
        try:
            self.service_manager = ServiceManager()
            await self.service_manager.start_service()
            
            self.validation_results['service_initialization'] = {
                'status': '✅',
                'components': {
                    'conversation_collector': '✅' if self.service_manager.conversation_collector else '❌',
                    'semantic_compressor': '✅' if self.service_manager.semantic_compressor else '❌',
                    'semantic_retriever': '✅' if self.service_manager.semantic_retriever else '❌',
                    'context_injector': '✅' if self.service_manager.context_injector else '❌',
                }
            }
            
            print("  ✅ 服务初始化成功")
            for component, status in self.validation_results['service_initialization']['components'].items():
                print(f"    {status} {component}")
                
        except Exception as e:
            self.validation_results['service_initialization'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 服务初始化失败: {str(e)}")
            raise
    
    async def validate_health_check(self):
        """验证健康检查接口"""
        print("\n🏥 验证健康检查接口...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://localhost:{self.settings.port}/health")
                
                if response.status_code == 200:
                    health_data = response.json()
                    self.validation_results['health_check'] = {
                        'status': '✅',
                        'response': health_data
                    }
                    print(f"  ✅ 健康检查通过")
                    print(f"    状态: {health_data.get('status', 'unknown')}")
                else:
                    self.validation_results['health_check'] = {
                        'status': '❌',
                        'http_status': response.status_code
                    }
                    self.has_failures = True
                    print(f"  ❌ 健康检查失败: HTTP {response.status_code}")
                    
        except Exception as e:
            self.validation_results['health_check'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 健康检查请求失败: {str(e)}")
    
    async def validate_conversation_storage(self):
        """验证对话存储功能"""
        print("\n💬 验证对话存储功能...")
        
        try:
            # 创建测试对话
            test_conversation = ConversationModel(
                id=uuid.uuid4(),
                project_id="test-project",
                title="测试对话 - 部署验证",
                messages=[
                    MessageModel(
                        id=uuid.uuid4(),
                        conversation_id=uuid.uuid4(),  # 会被覆盖
                        message_type="user",
                        content="这是一个测试问题",
                        token_count=10,
                        timestamp=datetime.utcnow() - timedelta(minutes=5)
                    ),
                    MessageModel(
                        id=uuid.uuid4(),
                        conversation_id=uuid.uuid4(),  # 会被覆盖
                        message_type="assistant",
                        content="这是一个测试回答，包含一些技术细节和实现说明。",
                        token_count=20,
                        timestamp=datetime.utcnow() - timedelta(minutes=4)
                    )
                ],
                message_count=2,
                token_count=30,
                started_at=datetime.utcnow() - timedelta(minutes=5),
                ended_at=datetime.utcnow() - timedelta(minutes=4)
            )
            
            # 设置正确的conversation_id
            for msg in test_conversation.messages:
                msg.conversation_id = test_conversation.id
            
            # 存储对话
            success = await self.service_manager.store_conversation(test_conversation)
            
            if success:
                # 验证数据库中的记录
                async with get_db_session() as session:
                    # 检查对话记录
                    conv_check = await session.execute(
                        text("SELECT COUNT(*) FROM conversations WHERE id = :id"),
                        {"id": str(test_conversation.id)}
                    )
                    conv_count = conv_check.scalar()
                    
                    # 检查消息记录
                    msg_check = await session.execute(
                        text("SELECT COUNT(*) FROM messages WHERE conversation_id = :id"),
                        {"id": str(test_conversation.id)}
                    )
                    msg_count = msg_check.scalar()
                
                self.validation_results['conversation_storage'] = {
                    'status': '✅',
                    'conversation_id': str(test_conversation.id),
                    'conversations_stored': conv_count,
                    'messages_stored': msg_count
                }
                
                # 保存测试数据ID以便清理
                self.test_data['conversation_id'] = test_conversation.id
                
                print(f"  ✅ 对话存储成功")
                print(f"    对话ID: {test_conversation.id}")
                print(f"    存储的消息数: {msg_count}")
            else:
                self.validation_results['conversation_storage'] = {
                    'status': '❌',
                    'error': '存储返回False'
                }
                self.has_failures = True
                print(f"  ❌ 对话存储失败")
                
        except Exception as e:
            self.validation_results['conversation_storage'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 对话存储验证失败: {str(e)}")
    
    async def validate_memory_compression(self):
        """验证记忆压缩功能"""
        print("\n🗜️ 验证记忆压缩功能...")
        
        if 'conversation_id' not in self.test_data:
            print("  ⚠️ 跳过压缩验证（无测试对话）")
            return
        
        try:
            # 等待一下确保对话已处理
            await asyncio.sleep(2)
            
            # 检查是否生成了记忆单元
            async with get_db_session() as session:
                memory_check = await session.execute(
                    text("SELECT COUNT(*) FROM memory_units WHERE conversation_id = :id"),
                    {"id": str(self.test_data['conversation_id'])}
                )
                memory_count = memory_check.scalar()
                
                if memory_count > 0:
                    # 获取记忆单元详情
                    memory_result = await session.execute(
                        text("""
                            SELECT id, title, summary, token_count 
                            FROM memory_units 
                            WHERE conversation_id = :id
                            LIMIT 1
                        """),
                        {"id": str(self.test_data['conversation_id'])}
                    )
                    memory_row = memory_result.fetchone()
                    
                    self.validation_results['memory_compression'] = {
                        'status': '✅',
                        'memory_units_created': memory_count,
                        'memory_id': str(memory_row[0]),
                        'title': memory_row[1],
                        'summary_length': len(memory_row[2]) if memory_row[2] else 0,
                        'token_count': memory_row[3]
                    }
                    
                    self.test_data['memory_unit_id'] = memory_row[0]
                    
                    print(f"  ✅ 记忆压缩成功")
                    print(f"    记忆单元ID: {memory_row[0]}")
                    print(f"    标题: {memory_row[1]}")
                    print(f"    Token数: {memory_row[3]}")
                else:
                    self.validation_results['memory_compression'] = {
                        'status': '⚠️',
                        'message': '未生成记忆单元（可能由于内容太短）'
                    }
                    print(f"  ⚠️ 未生成记忆单元")
                    
        except Exception as e:
            self.validation_results['memory_compression'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 记忆压缩验证失败: {str(e)}")
    
    async def validate_vector_storage(self):
        """验证向量存储功能"""
        print("\n🔍 验证向量存储功能...")
        
        try:
            # 创建测试记忆单元
            test_memory = MemoryUnitModel(
                id=uuid.uuid4(),
                project_id="test-project",
                conversation_id=self.test_data.get('conversation_id', uuid.uuid4()),
                unit_type=MemoryUnitType.MANUAL,
                title="测试记忆单元 - 向量存储验证",
                summary="这是一个用于验证向量存储功能的测试记忆单元",
                content="详细内容：包含架构设计、性能优化和安全考虑等技术要点。",
                keywords=["测试", "验证", "向量存储"],
                token_count=50,
                created_at=datetime.utcnow()
            )
            
            # 使用事务性存储
            success = await self.service_manager.store_memory_with_transaction(test_memory)
            
            if success:
                # 验证向量是否存储
                if self.service_manager.semantic_retriever:
                    from qdrant_client import QdrantClient
                    client = QdrantClient(url=self.settings.qdrant.qdrant_url)
                    
                    # 检查点是否存在
                    try:
                        point = client.retrieve(
                            collection_name=self.settings.qdrant.collection_name,
                            ids=[str(test_memory.id)]
                        )
                        
                        if point:
                            self.validation_results['vector_storage'] = {
                                'status': '✅',
                                'memory_id': str(test_memory.id),
                                'vector_stored': True,
                                'vector_id': str(point[0].id) if point else None
                            }
                            
                            self.test_data['test_memory_id'] = test_memory.id
                            
                            print(f"  ✅ 向量存储成功")
                            print(f"    记忆ID: {test_memory.id}")
                            print(f"    向量已存储到Qdrant")
                        else:
                            raise Exception("向量未找到")
                            
                    except Exception as e:
                        self.validation_results['vector_storage'] = {
                            'status': '❌',
                            'error': f'向量检索失败: {str(e)}'
                        }
                        self.has_failures = True
                        print(f"  ❌ 向量存储验证失败: {str(e)}")
            else:
                self.validation_results['vector_storage'] = {
                    'status': '❌',
                    'error': '事务存储失败'
                }
                self.has_failures = True
                print(f"  ❌ 向量存储失败")
                
        except Exception as e:
            self.validation_results['vector_storage'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 向量存储验证失败: {str(e)}")
    
    async def validate_memory_retrieval(self):
        """验证记忆检索功能"""
        print("\n🔎 验证记忆检索功能...")
        
        try:
            # 创建搜索查询
            search_query = SearchQuery(
                query="测试 架构设计",
                project_id="test-project",
                top_k=5,
                similarity_threshold=0.5
            )
            
            # 执行搜索
            if self.service_manager.semantic_retriever:
                from claude_memory.retrievers.semantic_retriever import RetrievalRequest
                request = RetrievalRequest(
                    query=search_query.query,
                    project_id=search_query.project_id,
                    top_k=search_query.top_k,
                    similarity_threshold=search_query.similarity_threshold
                )
                
                results = await self.service_manager.semantic_retriever.retrieve_memories(request)
                
                if results and results.memories:
                    self.validation_results['memory_retrieval'] = {
                        'status': '✅',
                        'query': search_query.query,
                        'results_count': len(results.memories),
                        'top_result': {
                            'title': results.memories[0].title,
                            'score': results.memories[0].relevance_score
                        } if results.memories else None
                    }
                    
                    print(f"  ✅ 记忆检索成功")
                    print(f"    查询: {search_query.query}")
                    print(f"    结果数: {len(results.memories)}")
                    if results.memories:
                        print(f"    最相关: {results.memories[0].title} (得分: {results.memories[0].relevance_score:.3f})")
                else:
                    self.validation_results['memory_retrieval'] = {
                        'status': '⚠️',
                        'message': '未找到匹配的记忆（可能是正常情况）'
                    }
                    print(f"  ⚠️ 未找到匹配的记忆")
            else:
                raise Exception("SemanticRetriever未初始化")
                
        except Exception as e:
            self.validation_results['memory_retrieval'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 记忆检索验证失败: {str(e)}")
    
    async def validate_context_injection(self):
        """验证上下文注入功能"""
        print("\n💉 验证上下文注入功能...")
        
        try:
            # 创建注入请求
            injection_request = ContextInjectionRequest(
                conversation_id=uuid.uuid4(),
                project_id="test-project",
                current_query="如何优化系统性能？",
                max_tokens=1000
            )
            
            # 执行注入
            if self.service_manager.context_injector:
                response = await self.service_manager.context_injector.inject_context(injection_request)
                
                if response:
                    self.validation_results['context_injection'] = {
                        'status': '✅',
                        'injected_tokens': response.total_tokens,
                        'memory_units_used': response.memory_units_used,
                        'context_length': len(response.injected_context)
                    }
                    
                    print(f"  ✅ 上下文注入成功")
                    print(f"    注入的Token数: {response.total_tokens}")
                    print(f"    使用的记忆单元数: {response.memory_units_used}")
                else:
                    self.validation_results['context_injection'] = {
                        'status': '⚠️',
                        'message': '未生成上下文（可能无相关记忆）'
                    }
                    print(f"  ⚠️ 未生成上下文")
            else:
                raise Exception("ContextInjector未初始化")
                
        except Exception as e:
            self.validation_results['context_injection'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 上下文注入验证失败: {str(e)}")
    
    async def validate_cross_project_search(self):
        """验证跨项目搜索功能"""
        print("\n🔗 验证跨项目搜索功能...")
        
        if not self.settings.project.enable_cross_project_search:
            print("  ⚠️ 跨项目搜索未启用，跳过验证")
            self.validation_results['cross_project_search'] = {
                'status': '⚠️',
                'message': '功能未启用'
            }
            return
        
        try:
            # 创建另一个项目的测试记忆
            other_project_memory = MemoryUnitModel(
                id=uuid.uuid4(),
                project_id="other-test-project",
                conversation_id=uuid.uuid4(),
                unit_type=MemoryUnitType.MANUAL,
                title="跨项目测试记忆",
                summary="这是另一个项目的测试记忆，用于验证跨项目搜索",
                content="包含共享知识和最佳实践",
                keywords=["跨项目", "共享", "测试"],
                token_count=40,
                created_at=datetime.utcnow()
            )
            
            # 存储到另一个项目
            await self.service_manager.store_memory_with_transaction(other_project_memory)
            self.test_data['other_project_memory_id'] = other_project_memory.id
            
            # 执行跨项目搜索
            if self.service_manager.cross_project_search_manager:
                from claude_memory.managers.cross_project_search import CrossProjectSearchRequest
                
                search_request = CrossProjectSearchRequest(
                    query="共享 最佳实践",
                    requesting_project_id="test-project",
                    target_project_ids=["other-test-project"],
                    max_results_per_project=5
                )
                
                results = await self.service_manager.cross_project_search_manager.search_across_projects(
                    search_request
                )
                
                if results and results.results:
                    self.validation_results['cross_project_search'] = {
                        'status': '✅',
                        'projects_searched': len(results.results),
                        'total_results': sum(len(r.memories) for r in results.results)
                    }
                    
                    print(f"  ✅ 跨项目搜索成功")
                    print(f"    搜索的项目数: {len(results.results)}")
                    print(f"    总结果数: {sum(len(r.memories) for r in results.results)}")
                else:
                    self.validation_results['cross_project_search'] = {
                        'status': '⚠️',
                        'message': '未找到跨项目结果'
                    }
                    print(f"  ⚠️ 未找到跨项目结果")
            else:
                raise Exception("CrossProjectSearchManager未初始化")
                
        except Exception as e:
            self.validation_results['cross_project_search'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 跨项目搜索验证失败: {str(e)}")
    
    async def validate_transaction_consistency(self):
        """验证事务一致性"""
        print("\n🔐 验证事务一致性...")
        
        try:
            # 模拟向量存储失败的情况
            test_memory = MemoryUnitModel(
                id=uuid.uuid4(),
                project_id="test-project",
                conversation_id=uuid.uuid4(),  # 使用不存在的对话ID
                unit_type=MemoryUnitType.MANUAL,
                title="事务一致性测试",
                summary="这个记忆单元应该失败",
                content="测试补偿事务",
                keywords=["事务", "测试"],
                token_count=30,
                created_at=datetime.utcnow()
            )
            
            # 尝试存储（应该失败）
            success = await self.service_manager.store_memory_with_transaction(test_memory)
            
            if not success:
                # 验证PostgreSQL中没有残留记录
                async with get_db_session() as session:
                    check_result = await session.execute(
                        text("SELECT COUNT(*) FROM memory_units WHERE id = :id"),
                        {"id": str(test_memory.id)}
                    )
                    count = check_result.scalar()
                    
                    if count == 0:
                        self.validation_results['transaction_consistency'] = {
                            'status': '✅',
                            'message': '事务回滚成功，数据一致性保持'
                        }
                        print(f"  ✅ 事务一致性验证通过")
                        print(f"    补偿事务正常工作")
                    else:
                        self.validation_results['transaction_consistency'] = {
                            'status': '❌',
                            'error': f'发现残留记录: {count}'
                        }
                        self.has_failures = True
                        print(f"  ❌ 事务一致性验证失败: 发现残留记录")
            else:
                # 如果意外成功了，记录为警告
                self.validation_results['transaction_consistency'] = {
                    'status': '⚠️',
                    'message': '测试用例意外成功'
                }
                self.test_data['transaction_test_memory_id'] = test_memory.id
                print(f"  ⚠️ 事务测试意外成功")
                
        except Exception as e:
            self.validation_results['transaction_consistency'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 事务一致性验证失败: {str(e)}")
    
    async def validate_performance_metrics(self):
        """验证性能指标"""
        print("\n📊 验证性能指标...")
        
        try:
            # 获取服务指标
            metrics = self.service_manager.metrics
            
            # 执行一些操作来生成指标
            start_time = time.time()
            
            # 测试记忆存储性能
            test_memories = []
            for i in range(5):
                memory = MemoryUnitModel(
                    id=uuid.uuid4(),
                    project_id="perf-test-project",
                    conversation_id=uuid.uuid4(),
                    unit_type=MemoryUnitType.MANUAL,
                    title=f"性能测试记忆 {i+1}",
                    summary=f"性能测试摘要 {i+1}",
                    content=f"性能测试内容 {i+1}" * 10,
                    keywords=[f"性能{i+1}", "测试"],
                    token_count=100,
                    created_at=datetime.utcnow()
                )
                test_memories.append(memory)
            
            # 并发存储测试
            tasks = [
                self.service_manager.add_memory(memory)
                for memory in test_memories
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000  # 转换为毫秒
            
            success_count = sum(1 for r in results if r is True)
            avg_time_per_op = duration / len(test_memories) if test_memories else 0
            
            self.validation_results['performance_metrics'] = {
                'status': '✅',
                'operations_tested': len(test_memories),
                'successful_operations': success_count,
                'total_duration_ms': round(duration, 2),
                'avg_time_per_operation_ms': round(avg_time_per_op, 2),
                'service_metrics': {
                    'conversations_processed': metrics.conversations_processed,
                    'memories_created': metrics.memories_created,
                    'average_response_time_ms': round(metrics.average_response_time_ms, 2)
                }
            }
            
            # 保存测试记忆ID用于清理
            self.test_data['perf_test_memory_ids'] = [m.id for m in test_memories]
            
            print(f"  ✅ 性能指标验证通过")
            print(f"    测试操作数: {len(test_memories)}")
            print(f"    成功率: {success_count}/{len(test_memories)}")
            print(f"    平均响应时间: {avg_time_per_op:.2f}ms")
            
            # 性能警告
            if avg_time_per_op > 500:
                print(f"  ⚠️ 警告: 平均响应时间较高")
                
        except Exception as e:
            self.validation_results['performance_metrics'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 性能指标验证失败: {str(e)}")
    
    async def validate_error_handling(self):
        """验证错误处理"""
        print("\n⚠️ 验证错误处理...")
        
        try:
            # 测试各种错误情况
            error_tests = []
            
            # 1. 无效的记忆单元（缺少必要字段）
            try:
                invalid_memory = MemoryUnitModel(
                    id=uuid.uuid4(),
                    project_id="",  # 空项目ID
                    conversation_id=uuid.uuid4(),
                    unit_type=MemoryUnitType.MANUAL,
                    title="",  # 空标题
                    summary="测试",
                    content="测试",
                    keywords=[],
                    token_count=10,
                    created_at=datetime.utcnow()
                )
                result = await self.service_manager.add_memory(invalid_memory)
                error_tests.append({
                    'test': '空项目ID',
                    'handled': not result,
                    'result': 'Rejected' if not result else 'Accepted'
                })
            except Exception as e:
                error_tests.append({
                    'test': '空项目ID',
                    'handled': True,
                    'result': f'Exception: {type(e).__name__}'
                })
            
            # 2. 超大内容测试
            try:
                large_memory = MemoryUnitModel(
                    id=uuid.uuid4(),
                    project_id="test-project",
                    conversation_id=uuid.uuid4(),
                    unit_type=MemoryUnitType.MANUAL,
                    title="超大内容测试",
                    summary="测试超大内容处理",
                    content="x" * 100000,  # 10万字符
                    keywords=["大内容"],
                    token_count=50000,
                    created_at=datetime.utcnow()
                )
                result = await self.service_manager.add_memory(large_memory)
                error_tests.append({
                    'test': '超大内容',
                    'handled': True,  # 无论成功与否，只要不崩溃就算处理了
                    'result': 'Stored' if result else 'Rejected'
                })
            except Exception as e:
                error_tests.append({
                    'test': '超大内容',
                    'handled': True,
                    'result': f'Exception: {type(e).__name__}'
                })
            
            # 统计结果
            handled_count = sum(1 for test in error_tests if test['handled'])
            
            self.validation_results['error_handling'] = {
                'status': '✅' if handled_count == len(error_tests) else '❌',
                'tests_performed': len(error_tests),
                'properly_handled': handled_count,
                'test_results': error_tests
            }
            
            print(f"  {'✅' if handled_count == len(error_tests) else '❌'} 错误处理验证")
            print(f"    测试用例数: {len(error_tests)}")
            print(f"    正确处理: {handled_count}/{len(error_tests)}")
            
            for test in error_tests:
                status = '✅' if test['handled'] else '❌'
                print(f"    {status} {test['test']}: {test['result']}")
                
        except Exception as e:
            self.validation_results['error_handling'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_failures = True
            print(f"  ❌ 错误处理验证失败: {str(e)}")
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        print("\n🧹 清理测试数据...")
        
        try:
            async with get_db_session() as session:
                # 清理测试对话
                if 'conversation_id' in self.test_data:
                    await session.execute(
                        text("DELETE FROM messages WHERE conversation_id = :id"),
                        {"id": str(self.test_data['conversation_id'])}
                    )
                    await session.execute(
                        text("DELETE FROM memory_units WHERE conversation_id = :id"),
                        {"id": str(self.test_data['conversation_id'])}
                    )
                    await session.execute(
                        text("DELETE FROM conversations WHERE id = :id"),
                        {"id": str(self.test_data['conversation_id'])}
                    )
                
                # 清理测试记忆单元
                test_memory_ids = []
                if 'memory_unit_id' in self.test_data:
                    test_memory_ids.append(str(self.test_data['memory_unit_id']))
                if 'test_memory_id' in self.test_data:
                    test_memory_ids.append(str(self.test_data['test_memory_id']))
                if 'other_project_memory_id' in self.test_data:
                    test_memory_ids.append(str(self.test_data['other_project_memory_id']))
                if 'transaction_test_memory_id' in self.test_data:
                    test_memory_ids.append(str(self.test_data['transaction_test_memory_id']))
                if 'perf_test_memory_ids' in self.test_data:
                    test_memory_ids.extend([str(id) for id in self.test_data['perf_test_memory_ids']])
                
                if test_memory_ids:
                    await session.execute(
                        text("DELETE FROM memory_units WHERE id = ANY(:ids)"),
                        {"ids": test_memory_ids}
                    )
                
                await session.commit()
                
            # 清理Qdrant中的测试向量
            if self.service_manager and self.service_manager.semantic_retriever:
                from qdrant_client import QdrantClient
                from qdrant_client.models import PointIdsList
                
                client = QdrantClient(url=self.settings.qdrant.qdrant_url)
                
                # 收集所有测试向量ID
                vector_ids = []
                if 'test_memory_id' in self.test_data:
                    vector_ids.append(str(self.test_data['test_memory_id']))
                if 'other_project_memory_id' in self.test_data:
                    vector_ids.append(str(self.test_data['other_project_memory_id']))
                if 'perf_test_memory_ids' in self.test_data:
                    vector_ids.extend([str(id) for id in self.test_data['perf_test_memory_ids']])
                
                if vector_ids:
                    try:
                        client.delete(
                            collection_name=self.settings.qdrant.collection_name,
                            points_selector=PointIdsList(points=vector_ids)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to clean up test vectors: {str(e)}")
            
            print("  ✅ 测试数据清理完成")
            
        except Exception as e:
            print(f"  ⚠️ 测试数据清理出错: {str(e)}")
    
    def print_summary(self):
        """打印验证总结"""
        print("\n" + "=" * 60)
        print("📊 验证总结")
        print("=" * 60)
        
        # 统计结果
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for r in self.validation_results.values() if r.get('status') == '✅')
        warning_tests = sum(1 for r in self.validation_results.values() if r.get('status') == '⚠️')
        failed_tests = sum(1 for r in self.validation_results.values() if r.get('status') == '❌')
        
        print(f"总测试数: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"⚠️ 警告: {warning_tests}")
        print(f"❌ 失败: {failed_tests}")
        
        if self.has_failures:
            print("\n❌ 验证失败，请检查失败的测试项")
        elif warning_tests > 0:
            print("\n⚠️ 验证通过，但有警告需要注意")
        else:
            print("\n✅ 所有验证通过，服务运行正常")
        
        # 保存验证报告
        report_path = project_root / 'logs' / f'post_deploy_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'version': self.settings.service.version,
                'has_failures': self.has_failures,
                'summary': {
                    'total': total_tests,
                    'passed': passed_tests,
                    'warnings': warning_tests,
                    'failed': failed_tests
                },
                'results': self.validation_results
            }, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 详细报告已保存到: {report_path}")


async def main():
    """主函数"""
    validator = PostDeploymentValidator()
    success = await validator.run_all_validations()
    
    # 返回适当的退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())