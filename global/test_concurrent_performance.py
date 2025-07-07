#!/usr/bin/env python3
"""
并发性能测试工具
测试Claude Memory MCP服务的并发访问性能和稳定性
"""

import asyncio
import time
import statistics
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import yaml

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from global_mcp.concurrent_memory_manager import ConcurrentMemoryManager, create_concurrent_manager


class ConcurrentPerformanceTester:
    """并发性能测试器"""
    
    def __init__(self):
        self.config = self.load_test_config()
        self.manager = None
        self.test_results = {}
        
    def load_test_config(self) -> Dict[str, Any]:
        """加载测试配置"""
        return {
            "database": {
                "url": "sqlite:///test_concurrent_memory.db"
            },
            "vector_store": {
                "url": "http://localhost:6333",
                "collection_name": "test_memories",
                "vector_size": 384
            },
            "concurrency": {
                "max_connections": 20,
                "cache_size": 2000,
                "cache_ttl": 300.0,
                "max_workers": 8
            },
            "memory": {
                "cross_project_sharing": True,
                "project_isolation": False,
                "retention_days": 365
            }
        }
    
    async def setup_test_data(self, num_projects: int = 10, conversations_per_project: int = 5):
        """设置大量测试数据"""
        print(f"📊 设置测试数据: {num_projects}个项目, 每个项目{conversations_per_project}个对话...")
        
        conversations_batch = []
        
        for project_idx in range(num_projects):
            project_name = f"test-project-{project_idx:03d}"
            project_path = f"/home/user/projects/{project_name}"
            
            project_context = {
                "project_name": project_name,
                "project_path": project_path,
                "project_type": "test"
            }
            
            for conv_idx in range(conversations_per_project):
                # 创建不同复杂度的对话
                num_messages = 3 + (conv_idx % 5)  # 3-7条消息
                messages = []
                
                for msg_idx in range(num_messages):
                    if msg_idx % 2 == 0:
                        # 用户消息
                        content = f"项目{project_idx}对话{conv_idx}的问题{msg_idx}: 关于数据库性能优化和用户认证的技术方案"
                        if project_idx % 3 == 0:
                            content += " React前端开发"
                        elif project_idx % 3 == 1:
                            content += " Python后端开发"
                        else:
                            content += " 数据分析处理"
                        
                        messages.append({
                            "role": "user",
                            "content": content,
                            "type": "user",
                            "metadata": {"message_index": msg_idx}
                        })
                    else:
                        # 助手回复
                        content = f"针对问题{msg_idx-1}的详细解答: 推荐使用现代化的技术栈，包括数据库连接池、缓存策略、用户认证最佳实践。"
                        content += f" 具体实现可以参考项目{project_idx}中的经验。"
                        
                        messages.append({
                            "role": "assistant", 
                            "content": content,
                            "type": "assistant",
                            "metadata": {"message_index": msg_idx}
                        })
                
                conversation_data = {
                    "title": f"项目{project_idx} - 技术讨论{conv_idx}",
                    "messages": messages,
                    "metadata": {
                        "test_data": True,
                        "project_index": project_idx,
                        "conversation_index": conv_idx
                    }
                }
                
                conversations_batch.append((conversation_data, project_context))
        
        # 批量存储所有对话
        start_time = time.time()
        conversation_ids = await self.manager.store_conversation_batch(conversations_batch)
        storage_time = time.time() - start_time
        
        print(f"✓ 数据设置完成: {len(conversation_ids)}个对话, 耗时: {storage_time:.2f}秒")
        return len(conversation_ids)
    
    async def test_concurrent_search(self, num_concurrent: int = 50, num_queries: int = 100) -> Dict[str, Any]:
        """测试并发搜索性能"""
        print(f"\n🔍 测试并发搜索: {num_concurrent}个并发请求, 总共{num_queries}次查询")
        
        search_queries = [
            "数据库性能优化",
            "用户认证",
            "React前端",
            "Python后端", 
            "数据分析",
            "技术方案",
            "缓存策略",
            "连接池",
            "最佳实践",
            "项目经验"
        ]
        
        async def single_search(query_id: int):
            """单个搜索任务"""
            query = search_queries[query_id % len(search_queries)]
            start_time = time.time()
            
            try:
                results = await self.manager.search_memories_concurrent(
                    query=query,
                    limit=10,
                    use_cache=True
                )
                duration = time.time() - start_time
                return {
                    "query_id": query_id,
                    "query": query,
                    "duration": duration,
                    "result_count": len(results),
                    "success": True,
                    "error": None
                }
            except Exception as e:
                duration = time.time() - start_time
                return {
                    "query_id": query_id,
                    "query": query,
                    "duration": duration,
                    "result_count": 0,
                    "success": False,
                    "error": str(e)
                }
        
        # 创建并发任务
        tasks = []
        for i in range(num_queries):
            task = single_search(i)
            tasks.append(task)
            
            # 控制并发数量
            if len(tasks) >= num_concurrent:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
                
                # 处理结果
                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"搜索任务异常: {result}")
        
        # 处理剩余任务
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 等待所有任务完成并收集结果
        start_time = time.time()
        all_tasks = [single_search(i) for i in range(num_queries)]
        results = await asyncio.gather(*all_tasks)
        total_time = time.time() - start_time
        
        # 分析结果
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        durations = [r["duration"] for r in successful_results]
        result_counts = [r["result_count"] for r in successful_results]
        
        analysis = {
            "total_queries": num_queries,
            "successful_queries": len(successful_results),
            "failed_queries": len(failed_results),
            "success_rate": len(successful_results) / num_queries,
            "total_time": total_time,
            "queries_per_second": num_queries / total_time,
            "avg_duration": statistics.mean(durations) if durations else 0,
            "median_duration": statistics.median(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "avg_result_count": statistics.mean(result_counts) if result_counts else 0,
            "errors": [r["error"] for r in failed_results]
        }
        
        print(f"搜索测试结果:")
        print(f"  成功率: {analysis['success_rate']:.1%}")
        print(f"  总耗时: {analysis['total_time']:.2f}秒")
        print(f"  查询速率: {analysis['queries_per_second']:.1f} QPS")
        print(f"  平均响应时间: {analysis['avg_duration']*1000:.1f}ms")
        print(f"  响应时间中位数: {analysis['median_duration']*1000:.1f}ms")
        print(f"  平均结果数: {analysis['avg_result_count']:.1f}")
        
        return analysis
    
    async def test_mixed_workload(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """测试混合工作负载"""
        print(f"\n🔄 测试混合工作负载: {duration_seconds}秒持续压力测试")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        stats = {
            "search_requests": 0,
            "recent_requests": 0,
            "total_requests": 0,
            "errors": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        async def search_worker():
            """搜索工作负载"""
            search_queries = ["数据库", "认证", "React", "Python", "优化"]
            while time.time() < end_time:
                try:
                    query = search_queries[stats["search_requests"] % len(search_queries)]
                    await self.manager.search_memories_concurrent(query, limit=5)
                    stats["search_requests"] += 1
                    stats["total_requests"] += 1
                except Exception:
                    stats["errors"] += 1
                await asyncio.sleep(0.1)  # 小延迟
        
        async def recent_worker():
            """最近对话工作负载"""
            while time.time() < end_time:
                try:
                    await self.manager.get_recent_conversations_concurrent(limit=10)
                    stats["recent_requests"] += 1
                    stats["total_requests"] += 1
                except Exception:
                    stats["errors"] += 1
                await asyncio.sleep(0.2)  # 不同的延迟模式
        
        # 启动多个工作负载
        workers = []
        for _ in range(10):  # 10个搜索工作者
            workers.append(asyncio.create_task(search_worker()))
        for _ in range(5):   # 5个最近对话工作者
            workers.append(asyncio.create_task(recent_worker()))
        
        # 等待测试完成
        await asyncio.sleep(duration_seconds + 1)
        
        # 取消所有工作者
        for worker in workers:
            worker.cancel()
        
        # 等待工作者清理
        await asyncio.gather(*workers, return_exceptions=True)
        
        # 计算结果
        actual_duration = time.time() - start_time
        total_qps = stats["total_requests"] / actual_duration
        error_rate = stats["errors"] / max(stats["total_requests"], 1)
        
        print(f"混合负载测试结果:")
        print(f"  总请求数: {stats['total_requests']}")
        print(f"  搜索请求: {stats['search_requests']}")
        print(f"  最近对话请求: {stats['recent_requests']}")
        print(f"  错误数: {stats['errors']}")
        print(f"  错误率: {error_rate:.1%}")
        print(f"  总QPS: {total_qps:.1f}")
        
        return {
            **stats,
            "duration": actual_duration,
            "total_qps": total_qps,
            "error_rate": error_rate
        }
    
    async def test_cache_performance(self) -> Dict[str, Any]:
        """测试缓存性能"""
        print(f"\n💾 测试缓存性能")
        
        # 执行一些搜索来填充缓存
        queries = ["数据库", "认证", "React", "Python", "优化"]
        
        # 第一轮：缓存未命中
        print("第一轮搜索 (缓存未命中)...")
        first_round_times = []
        for query in queries:
            start_time = time.time()
            await self.manager.search_memories_concurrent(query, use_cache=False)
            duration = time.time() - start_time
            first_round_times.append(duration)
        
        # 第二轮：缓存命中
        print("第二轮搜索 (缓存命中)...")
        second_round_times = []
        for query in queries:
            start_time = time.time()
            await self.manager.search_memories_concurrent(query, use_cache=True)
            duration = time.time() - start_time
            second_round_times.append(duration)
        
        avg_uncached = statistics.mean(first_round_times)
        avg_cached = statistics.mean(second_round_times)
        speedup = avg_uncached / avg_cached if avg_cached > 0 else 0
        
        print(f"缓存性能结果:")
        print(f"  未缓存平均时间: {avg_uncached*1000:.1f}ms")
        print(f"  缓存命中平均时间: {avg_cached*1000:.1f}ms")
        print(f"  缓存加速比: {speedup:.1f}x")
        
        return {
            "avg_uncached_time": avg_uncached,
            "avg_cached_time": avg_cached,
            "cache_speedup": speedup,
            "first_round_times": first_round_times,
            "second_round_times": second_round_times
        }
    
    async def test_connection_pool_efficiency(self) -> Dict[str, Any]:
        """测试连接池效率"""
        print(f"\n🔌 测试连接池效率")
        
        # 创建大量并发请求来测试连接池
        async def db_task():
            try:
                await self.manager.search_memories_concurrent("test", limit=1)
                return True
            except Exception:
                return False
        
        # 测试不同并发级别
        concurrency_levels = [5, 10, 20, 50]
        results = {}
        
        for level in concurrency_levels:
            print(f"测试并发级别: {level}")
            start_time = time.time()
            
            tasks = [db_task() for _ in range(level)]
            task_results = await asyncio.gather(*tasks)
            
            duration = time.time() - start_time
            success_count = sum(task_results)
            success_rate = success_count / level
            
            results[level] = {
                "duration": duration,
                "success_count": success_count,
                "success_rate": success_rate,
                "requests_per_second": level / duration
            }
            
            print(f"  耗时: {duration:.2f}s, 成功率: {success_rate:.1%}")
        
        return results
    
    async def run_comprehensive_test(self):
        """运行综合测试"""
        print("🧪 开始Claude Memory MCP并发性能综合测试")
        print("=" * 80)
        
        try:
            # 初始化管理器
            print("⚙️  初始化并发记忆管理器...")
            self.manager = create_concurrent_manager(self.config)
            await self.manager.initialize()
            print("✓ 管理器初始化完成")
            
            # 设置测试数据
            num_conversations = await self.setup_test_data(
                num_projects=20, 
                conversations_per_project=10
            )
            
            # 执行各项测试
            print(f"\n开始性能测试 (数据集: {num_conversations}个对话)...")
            
            # 1. 并发搜索测试
            search_results = await self.test_concurrent_search(
                num_concurrent=30, 
                num_queries=200
            )
            
            # 2. 混合工作负载测试
            mixed_results = await self.test_mixed_workload(duration_seconds=30)
            
            # 3. 缓存性能测试
            cache_results = await self.test_cache_performance()
            
            # 4. 连接池效率测试
            pool_results = await self.test_connection_pool_efficiency()
            
            # 5. 获取系统性能统计
            perf_stats = await self.manager.get_performance_stats()
            
            # 6. 健康检查
            health_check = await self.manager.health_check_concurrent()
            
            # 生成综合报告
            await self.generate_performance_report({
                "test_config": self.config,
                "data_setup": {"num_conversations": num_conversations},
                "concurrent_search": search_results,
                "mixed_workload": mixed_results,
                "cache_performance": cache_results,
                "connection_pool": pool_results,
                "system_stats": perf_stats,
                "health_check": health_check
            })
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {e}")
            raise
        finally:
            if self.manager:
                await self.manager.close()
    
    async def generate_performance_report(self, test_data: Dict[str, Any]):
        """生成性能测试报告"""
        print(f"\n📊 生成性能测试报告...")
        
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "test_summary": {
                "concurrent_search_qps": test_data["concurrent_search"]["queries_per_second"],
                "search_success_rate": test_data["concurrent_search"]["success_rate"],
                "avg_response_time_ms": test_data["concurrent_search"]["avg_duration"] * 1000,
                "cache_speedup": test_data["cache_performance"]["cache_speedup"],
                "mixed_workload_qps": test_data["mixed_workload"]["total_qps"],
                "system_health": test_data["health_check"]["status"]
            },
            "detailed_results": test_data
        }
        
        # 保存报告
        report_file = Path(__file__).parent / "test_results" / f"concurrent_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 性能测试报告已保存: {report_file}")
        
        # 输出关键指标总结
        print(f"\n🎯 并发性能测试总结:")
        print(f"  ✅ 并发搜索QPS: {report['test_summary']['concurrent_search_qps']:.1f}")
        print(f"  ✅ 搜索成功率: {report['test_summary']['search_success_rate']:.1%}")
        print(f"  ✅ 平均响应时间: {report['test_summary']['avg_response_time_ms']:.1f}ms")
        print(f"  ✅ 缓存加速比: {report['test_summary']['cache_speedup']:.1f}x")
        print(f"  ✅ 混合负载QPS: {report['test_summary']['mixed_workload_qps']:.1f}")
        print(f"  ✅ 系统健康状态: {report['test_summary']['system_health']}")
        
        # 性能基准评估
        print(f"\n📈 性能基准评估:")
        if report['test_summary']['concurrent_search_qps'] >= 50:
            print("  🟢 并发搜索性能: 优秀 (≥50 QPS)")
        elif report['test_summary']['concurrent_search_qps'] >= 20:
            print("  🟡 并发搜索性能: 良好 (≥20 QPS)")
        else:
            print("  🟠 并发搜索性能: 需要优化 (<20 QPS)")
        
        if report['test_summary']['avg_response_time_ms'] <= 100:
            print("  🟢 响应时间: 优秀 (≤100ms)")
        elif report['test_summary']['avg_response_time_ms'] <= 500:
            print("  🟡 响应时间: 良好 (≤500ms)")
        else:
            print("  🟠 响应时间: 需要优化 (>500ms)")
        
        if report['test_summary']['cache_speedup'] >= 5:
            print("  🟢 缓存效果: 优秀 (≥5x加速)")
        elif report['test_summary']['cache_speedup'] >= 2:
            print("  🟡 缓存效果: 良好 (≥2x加速)")
        else:
            print("  🟠 缓存效果: 需要优化 (<2x加速)")


async def main():
    """主函数"""
    tester = ConcurrentPerformanceTester()
    
    try:
        await tester.run_comprehensive_test()
        print(f"\n🎉 Claude Memory MCP并发性能测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())