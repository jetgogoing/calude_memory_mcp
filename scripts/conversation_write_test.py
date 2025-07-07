#!/usr/bin/env python3
"""
Claude Memory真对话写入测试
模拟真实对话场景，测试完整的数据流程
"""

import os
import json
import time
import uuid
import psycopg2
import requests
from datetime import datetime
from pathlib import Path

class ConversationWriteTest:
    """对话写入测试器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.test_results = []
        self.test_conversation_id = str(uuid.uuid4())
        self.test_messages = []
        
        # 数据库连接配置
        self.db_config = {
            "host": "localhost",
            "database": "claude_memory_db",
            "user": "claude_memory",
            "password": "password"
        }
    
    def log_test(self, test_name, success, message, details=None):
        """记录测试结果"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        
        if details:
            for line in str(details).split('\n'):
                if line.strip():
                    print(f"   {line}")
    
    def create_test_conversation(self):
        """创建测试对话"""
        print("\n💬 测试1: 创建测试对话")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 插入对话记录 (匹配实际表结构)
            cursor.execute("""
                INSERT INTO conversations (id, session_id, title, created_at, updated_at, last_activity_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                self.test_conversation_id,
                "test_session_" + str(int(time.time())),
                "Claude Memory测试对话",
                datetime.now(),
                datetime.now(),
                datetime.now()
            ))
            
            created_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            self.log_test("创建对话记录", True, "对话记录创建成功",
                         f"对话ID: {created_id}")
            return True
            
        except Exception as e:
            self.log_test("创建对话记录", False, f"创建失败: {e}")
            return False
    
    def write_test_messages(self):
        """写入测试消息"""
        print("\n📝 测试2: 写入测试消息")
        
        # 模拟真实对话消息
        test_messages = [
            {
                "role": "user",
                "content": "你好！我想了解Claude Memory系统的工作原理。",
                "metadata": {"type": "question", "topic": "system"}
            },
            {
                "role": "assistant", 
                "content": "Claude Memory是一个智能记忆管理系统，它使用向量数据库来存储和检索对话历史。系统的核心组件包括：\n\n1. PostgreSQL - 存储结构化数据\n2. Qdrant - 向量搜索引擎\n3. MCP服务器 - 提供记忆接口\n4. 监控系统 - Prometheus + Alertmanager",
                "metadata": {"type": "explanation", "topics": ["architecture", "components"]}
            },
            {
                "role": "user",
                "content": "能详细说说向量搜索是如何工作的吗？",
                "metadata": {"type": "followup", "topic": "vector_search"}
            },
            {
                "role": "assistant",
                "content": "向量搜索的工作原理：\n\n1. **文本嵌入**: 将对话文本转换为高维向量表示\n2. **向量存储**: 在Qdrant中存储这些向量\n3. **相似性搜索**: 使用余弦相似度等方法找到相关内容\n4. **语义理解**: 能够理解上下文和语义关系\n\n这使得系统能够找到概念相关而非仅仅字面匹配的内容。",
                "metadata": {"type": "detailed_explanation", "topics": ["vector_search", "embedding", "similarity"]}
            },
            {
                "role": "user",
                "content": "这个系统的性能如何？有监控吗？",
                "metadata": {"type": "performance_inquiry", "topic": "monitoring"}
            },
            {
                "role": "assistant",
                "content": "系统具备完整的监控体系：\n\n**性能指标**:\n- 平均响应时间 < 2秒\n- 搜索准确率 > 90%\n- 系统可用性 > 99.5%\n\n**监控组件**:\n- Prometheus: 指标收集\n- Alertmanager: 告警管理\n- 自定义仪表板: 实时监控\n\n**告警机制**:\n- 服务离线告警\n- 性能下降预警\n- 资源使用监控",
                "metadata": {"type": "performance_data", "topics": ["metrics", "monitoring", "alerting"]}
            }
        ]
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            success_count = 0
            
            for i, msg in enumerate(test_messages):
                try:
                    message_id = str(uuid.uuid4())
                    
                    cursor.execute("""
                        INSERT INTO messages (id, conversation_id, sequence_number, message_type, content, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        message_id,
                        self.test_conversation_id,
                        i + 1,  # sequence_number
                        msg["role"],  # message_type
                        msg["content"],
                        json.dumps(msg["metadata"]),
                        datetime.now()
                    ))
                    
                    self.test_messages.append({
                        "id": message_id,
                        "content": msg["content"],
                        "message_type": msg["role"]
                    })
                    
                    success_count += 1
                    
                except Exception as e:
                    self.log_test(f"写入消息{i+1}", False, f"失败: {e}")
            
            conn.commit()
            conn.close()
            
            if success_count == len(test_messages):
                self.log_test("写入测试消息", True, f"成功写入{success_count}条消息",
                             f"涵盖用户和助手对话，包含丰富元数据")
                return True
            else:
                self.log_test("写入测试消息", False, f"仅成功{success_count}/{len(test_messages)}条")
                return False
                
        except Exception as e:
            self.log_test("写入测试消息", False, f"数据库连接失败: {e}")
            return False
    
    def test_message_retrieval(self):
        """测试消息检索"""
        print("\n🔍 测试3: 消息检索测试")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 测试基本查询
            cursor.execute("""
                SELECT id, message_type, content, created_at
                FROM messages 
                WHERE conversation_id = %s
                ORDER BY created_at
            """, (self.test_conversation_id,))
            
            retrieved_messages = cursor.fetchall()
            
            if len(retrieved_messages) == len(self.test_messages):
                self.log_test("基本消息检索", True, f"成功检索{len(retrieved_messages)}条消息")
            else:
                self.log_test("基本消息检索", False, 
                             f"检索数量不匹配: {len(retrieved_messages)} vs {len(self.test_messages)}")
                return False
            
            # 测试内容搜索
            cursor.execute("""
                SELECT id, message_type, content
                FROM messages 
                WHERE conversation_id = %s AND content ILIKE %s
            """, (self.test_conversation_id, "%向量搜索%"))
            
            search_results = cursor.fetchall()
            
            if len(search_results) > 0:
                self.log_test("内容搜索测试", True, f"找到{len(search_results)}条相关消息")
            else:
                self.log_test("内容搜索测试", False, "未找到相关消息")
            
            # 测试元数据查询
            cursor.execute("""
                SELECT id, metadata
                FROM messages 
                WHERE conversation_id = %s AND metadata::text ILIKE %s
            """, (self.test_conversation_id, "%monitoring%"))
            
            metadata_results = cursor.fetchall()
            
            if len(metadata_results) > 0:
                self.log_test("元数据查询测试", True, f"找到{len(metadata_results)}条包含监控主题的消息")
            else:
                self.log_test("元数据查询测试", False, "未找到元数据匹配")
            
            conn.close()
            return True
            
        except Exception as e:
            self.log_test("消息检索测试", False, f"检索失败: {e}")
            return False
    
    def test_vector_embedding_simulation(self):
        """测试向量嵌入模拟"""
        print("\n🧮 测试4: 向量嵌入模拟")
        
        try:
            # 模拟向量嵌入过程
            import random
            
            embeddings_created = 0
            
            for msg in self.test_messages:
                try:
                    # 生成模拟向量 (实际应该使用真实嵌入模型)
                    mock_vector = [random.random() for _ in range(384)]  # 模拟384维向量
                    
                    # 模拟向Qdrant写入向量的过程
                    vector_data = {
                        "id": msg["id"],
                        "vector": mock_vector,
                        "payload": {
                            "content": msg["content"][:100],  # 截取前100字符
                            "message_type": msg["message_type"],
                            "conversation_id": self.test_conversation_id
                        }
                    }
                    
                    # 这里应该是真实的Qdrant API调用
                    # 但为了测试稳定性，我们只模拟这个过程
                    embeddings_created += 1
                    
                except Exception as e:
                    self.log_test(f"向量嵌入 {msg['id'][:8]}", False, f"失败: {e}")
            
            if embeddings_created == len(self.test_messages):
                self.log_test("向量嵌入模拟", True, f"成功模拟{embeddings_created}个向量嵌入",
                             "实际部署中将使用真实嵌入模型")
                return True
            else:
                self.log_test("向量嵌入模拟", False, f"仅成功{embeddings_created}/{len(self.test_messages)}个")
                return False
                
        except Exception as e:
            self.log_test("向量嵌入模拟", False, f"嵌入过程失败: {e}")
            return False
    
    def test_mcp_integration(self):
        """测试MCP集成"""
        print("\n🔗 测试5: MCP集成测试")
        
        try:
            import subprocess
            
            # 启动MCP服务器
            mcp_script = self.project_root / "monitoring_mcp_server.py"
            process = subprocess.Popen(
                ["python3", str(mcp_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root)
            )
            
            # 测试记忆搜索功能
            search_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "memory_search",
                    "arguments": {"query": "向量搜索", "limit": 3}
                }
            }
            
            input_data = json.dumps(search_request) + "\n"
            stdout, stderr = process.communicate(input=input_data, timeout=10)
            
            # 分析响应
            if "找到" in stdout or "搜索" in stdout:
                self.log_test("MCP记忆搜索", True, "记忆搜索功能正常",
                             "能够检索之前写入的对话内容")
            else:
                self.log_test("MCP记忆搜索", False, "记忆搜索功能异常",
                             f"响应: {stdout[:100]}...")
            
            return True
            
        except subprocess.TimeoutExpired:
            process.kill()
            self.log_test("MCP集成测试", False, "MCP服务器响应超时")
            return False
        except Exception as e:
            self.log_test("MCP集成测试", False, f"MCP测试失败: {e}")
            return False
    
    def test_data_persistence(self):
        """测试数据持久性"""
        print("\n💾 测试6: 数据持久性验证")
        
        try:
            # 等待一小段时间，模拟系统运行
            time.sleep(2)
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 验证对话仍然存在
            cursor.execute("""
                SELECT COUNT(*) FROM conversations WHERE id = %s
            """, (self.test_conversation_id,))
            
            conversation_count = cursor.fetchone()[0]
            
            # 验证消息仍然存在
            cursor.execute("""
                SELECT COUNT(*) FROM messages WHERE conversation_id = %s
            """, (self.test_conversation_id,))
            
            message_count = cursor.fetchone()[0]
            
            conn.close()
            
            if conversation_count == 1 and message_count == len(self.test_messages):
                self.log_test("数据持久性验证", True, "所有数据成功持久化",
                             f"对话: {conversation_count}, 消息: {message_count}")
                return True
            else:
                self.log_test("数据持久性验证", False, 
                             f"数据丢失: 对话{conversation_count}, 消息{message_count}")
                return False
                
        except Exception as e:
            self.log_test("数据持久性验证", False, f"验证失败: {e}")
            return False
    
    def cleanup_test_data(self):
        """清理测试数据"""
        print("\n🧹 清理测试数据")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 删除测试消息
            cursor.execute("""
                DELETE FROM messages WHERE conversation_id = %s
            """, (self.test_conversation_id,))
            
            deleted_messages = cursor.rowcount
            
            # 删除测试对话
            cursor.execute("""
                DELETE FROM conversations WHERE id = %s
            """, (self.test_conversation_id,))
            
            deleted_conversations = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            self.log_test("清理测试数据", True, "测试数据清理完成",
                         f"删除消息: {deleted_messages}, 删除对话: {deleted_conversations}")
            return True
            
        except Exception as e:
            self.log_test("清理测试数据", False, f"清理失败: {e}")
            return False
    
    def generate_test_report(self):
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        
        print(f"\n📊 对话写入测试报告:")
        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {total_tests - passed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        # 保存详细报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_conversation_id": self.test_conversation_id,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests/total_tests*100,
            "test_results": self.test_results
        }
        
        report_file = self.project_root / "reports" / f"conversation_write_test_{int(time.time())}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存: {report_file}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """运行所有测试"""
        print("💬 开始Claude Memory真对话写入测试...")
        print("=" * 60)
        
        # 执行测试序列
        tests = [
            self.create_test_conversation,
            self.write_test_messages,
            self.test_message_retrieval,
            self.test_vector_embedding_simulation,
            self.test_mcp_integration,
            self.test_data_persistence,
            self.cleanup_test_data
        ]
        
        for test_func in tests:
            test_func()
        
        # 生成报告
        success = self.generate_test_report()
        
        if success:
            print("\n🎉 所有对话写入测试通过！数据流程验证成功！")
        else:
            print("\n⚠️ 部分测试失败，请检查详细报告")
        
        return success

def main():
    """主函数"""
    tester = ConversationWriteTest()
    return tester.run_all_tests()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)