#!/usr/bin/env python3
"""
性能优化功能演示
展示Claude Memory MCP服务的并发优化、缓存策略和自动扩展能力
"""

import asyncio
import time
import statistics
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from global_mcp.concurrent_memory_manager import ConcurrentMemoryManager, create_concurrent_manager


class PerformanceOptimizationDemo:
    """性能优化演示"""
    
    def __init__(self):
        self.config = self.load_demo_config()
        self.manager = None
        
    def load_demo_config(self) -> Dict[str, Any]:
        """加载演示配置"""
        return {
            "database": {
                "url": "sqlite:///demo_performance.db"
            },
            "vector_store": {
                "url": "http://localhost:6333",
                "collection_name": "demo_memories"
            },
            "concurrency": {
                "max_connections": 15,
                "cache_size": 1000,
                "cache_ttl": 120.0,
                "max_workers": 6
            },
            "memory": {
                "cross_project_sharing": True,
                "project_isolation": False,
                "retention_days": 365
            }
        }
    
    async def setup_demo_data(self):
        """设置演示数据"""
        print("📊 设置性能优化演示数据...")
        
        # 创建演示对话数据
        conversations_data = []
        
        for i in range(50):  # 50个对话
            project_context = {
                "project_name": f"project-{i % 5}",  # 5个项目
                "project_path": f"/demo/project-{i % 5}",
                "project_type": "demo"
            }
            
            conversation_data = {
                "title": f"演示对话 {i}",
                "messages": [
                    {
                        "role": "user",
                        "content": f"这是演示问题 {i}，关于性能优化、缓存策略和并发处理的讨论。"
                    },
                    {
                        "role": "assistant", 
                        "content": f"关于问题 {i} 的回答：性能优化需要考虑多个方面，包括数据库索引、缓存机制、连接池管理等。"
                    }
                ],
                "metadata": {"demo": True, "batch": i // 10}
            }
            
            conversations_data.append((conversation_data, project_context))
        
        # 批量存储
        start_time = time.time()
        conversation_ids = await self.manager.store_conversation_batch(conversations_data)
        storage_time = time.time() - start_time
        
        print(f"✓ 演示数据创建完成: {len(conversation_ids)}个对话, 耗时: {storage_time:.2f}秒")
        return len(conversation_ids)
    
    async def demo_cache_optimization(self):
        """演示缓存优化"""
        print("\n💾 缓存优化演示")
        print("-" * 50)
        
        test_queries = ["性能优化", "缓存策略", "并发处理", "数据库", "连接池"]
        
        # 第一轮：无缓存查询
        print("🔍 第一轮查询 (缓存未命中):")
        uncached_times = []
        for query in test_queries:
            start_time = time.time()
            results = await self.manager.search_memories_concurrent(query, use_cache=False)
            duration = time.time() - start_time
            uncached_times.append(duration)
            print(f"  '{query}': {duration*1000:.1f}ms, {len(results)}条结果")
        
        # 短暂等待确保缓存生效
        await asyncio.sleep(0.1)
        
        # 第二轮：缓存命中
        print("\n🚀 第二轮查询 (缓存命中):")
        cached_times = []
        for query in test_queries:
            start_time = time.time()
            results = await self.manager.search_memories_concurrent(query, use_cache=True)
            duration = time.time() - start_time
            cached_times.append(duration)
            print(f"  '{query}': {duration*1000:.1f}ms, {len(results)}条结果")
        
        # 分析缓存效果
        avg_uncached = statistics.mean(uncached_times)
        avg_cached = statistics.mean(cached_times)
        speedup = avg_uncached / avg_cached if avg_cached > 0 else 0
        
        print(f"\n📈 缓存优化效果:")
        print(f"  未缓存平均时间: {avg_uncached*1000:.1f}ms")
        print(f"  缓存命中平均时间: {avg_cached*1000:.1f}ms")
        print(f"  性能提升: {speedup:.1f}x")
        print(f"  时间节省: {((avg_uncached - avg_cached) / avg_uncached * 100):.1f}%")
        
        return {
            "avg_uncached_time": avg_uncached,
            "avg_cached_time": avg_cached,
            "speedup": speedup,
            "time_saved_percent": ((avg_uncached - avg_cached) / avg_uncached * 100) if avg_uncached > 0 else 0
        }
    
    async def demo_concurrent_processing(self):
        """演示并发处理能力"""
        print("\n⚡ 并发处理演示")
        print("-" * 50)
        
        # 测试不同并发级别
        concurrency_levels = [1, 5, 10, 20]
        results = {}
        
        for level in concurrency_levels:
            print(f"\n🔄 测试并发级别: {level}")
            
            async def single_request():
                query = "性能优化"
                start_time = time.time()
                await self.manager.search_memories_concurrent(query)
                return time.time() - start_time
            
            # 执行并发请求
            start_time = time.time()
            tasks = [single_request() for _ in range(level)]
            request_times = await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            avg_request_time = statistics.mean(request_times)
            throughput = level / total_time
            
            results[level] = {
                "total_time": total_time,
                "avg_request_time": avg_request_time,
                "throughput": throughput
            }
            
            print(f"  总耗时: {total_time:.2f}s")
            print(f"  平均请求时间: {avg_request_time*1000:.1f}ms")
            print(f"  吞吐量: {throughput:.1f} 请求/秒")
        
        # 分析并发效果
        baseline_throughput = results[1]["throughput"]
        max_throughput = max(r["throughput"] for r in results.values())
        optimal_concurrency = max(results.keys(), key=lambda k: results[k]["throughput"])
        
        print(f"\n📊 并发处理分析:")
        print(f"  基准吞吐量 (并发=1): {baseline_throughput:.1f} 请求/秒")
        print(f"  最大吞吐量: {max_throughput:.1f} 请求/秒")
        print(f"  最优并发级别: {optimal_concurrency}")
        print(f"  并发提升倍数: {max_throughput / baseline_throughput:.1f}x")
        
        return results
    
    async def demo_batch_processing(self):
        """演示批处理优化"""
        print("\n📦 批处理优化演示")
        print("-" * 50)
        
        # 准备批量数据
        batch_conversations = []
        for i in range(20):
            project_context = {
                "project_name": f"batch-project-{i % 3}",
                "project_path": f"/demo/batch-{i % 3}",
                "project_type": "batch"
            }
            
            conversation_data = {
                "title": f"批处理对话 {i}",
                "messages": [
                    {"role": "user", "content": f"批处理问题 {i}"},
                    {"role": "assistant", "content": f"批处理回答 {i}"}
                ],
                "metadata": {"batch_demo": True}
            }
            
            batch_conversations.append((conversation_data, project_context))
        
        # 测试逐个存储 vs 批量存储
        print("🐌 逐个存储测试:")
        start_time = time.time()
        for conv_data, proj_context in batch_conversations[:10]:
            # 模拟逐个存储（实际使用批量接口但每次只存一个）
            await self.manager.store_conversation_batch([(conv_data, proj_context)])
        individual_time = time.time() - start_time
        
        print(f"  10个对话逐个存储耗时: {individual_time:.2f}s")
        
        print("\n🚀 批量存储测试:")
        start_time = time.time()
        await self.manager.store_conversation_batch(batch_conversations[10:])
        batch_time = time.time() - start_time
        
        print(f"  10个对话批量存储耗时: {batch_time:.2f}s")
        
        speedup = individual_time / batch_time if batch_time > 0 else 0
        print(f"\n📈 批处理优化效果:")
        print(f"  批处理加速比: {speedup:.1f}x")
        print(f"  效率提升: {((individual_time - batch_time) / individual_time * 100):.1f}%")
        
        return {
            "individual_time": individual_time,
            "batch_time": batch_time,
            "speedup": speedup
        }
    
    async def demo_performance_monitoring(self):
        """演示性能监控"""
        print("\n📊 性能监控演示")
        print("-" * 50)
        
        # 获取系统性能统计
        perf_stats = await self.manager.get_performance_stats()
        
        print("🔍 当前系统状态:")
        print(f"  并发统计:")
        concurrent_stats = perf_stats["concurrent_stats"]
        print(f"    总请求数: {concurrent_stats['total_requests']}")
        print(f"    当前并发: {concurrent_stats['concurrent_requests']}")
        print(f"    最大并发: {concurrent_stats['max_concurrent']}")
        print(f"    平均响应时间: {concurrent_stats['avg_response_time']*1000:.1f}ms")
        print(f"    错误数: {concurrent_stats['error_count']}")
        
        print(f"\n  缓存统计:")
        cache_stats = perf_stats["cache_stats"]
        print(f"    缓存大小: {cache_stats['cache_size']}/{cache_stats['max_size']}")
        print(f"    命中次数: {cache_stats['hits']}")
        print(f"    未命中次数: {cache_stats['misses']}")
        print(f"    命中率: {cache_stats['hit_rate']:.1%}")
        print(f"    淘汰次数: {cache_stats['evictions']}")
        
        print(f"\n  连接池统计:")
        pool_stats = perf_stats["connection_pool"]
        print(f"    当前连接数: {pool_stats['total_connections']}")
        print(f"    最大连接数: {pool_stats['max_connections']}")
        print(f"    队列大小: {pool_stats['queue_size']}")
        
        # 健康检查
        health_check = await self.manager.health_check_concurrent()
        print(f"\n🏥 系统健康检查:")
        print(f"  总体状态: {health_check['status']}")
        for check_name, check_result in health_check["checks"].items():
            status_icon = "✅" if check_result["status"] == "ok" else "❌"
            print(f"  {check_name}: {status_icon} {check_result['status']}")
        
        return {
            "performance_stats": perf_stats,
            "health_check": health_check
        }
    
    async def run_complete_demo(self):
        """运行完整演示"""
        print("🎯 Claude Memory MCP 性能优化完整演示")
        print("=" * 80)
        
        try:
            # 初始化管理器
            print("⚙️  初始化并发优化记忆管理器...")
            self.manager = create_concurrent_manager(self.config)
            await self.manager.initialize()
            print("✓ 管理器初始化完成")
            
            # 设置演示数据
            num_conversations = await self.setup_demo_data()
            
            # 执行各项演示
            print(f"\n开始性能优化演示 (数据集: {num_conversations}个对话)...")
            
            # 1. 缓存优化演示
            cache_results = await self.demo_cache_optimization()
            
            # 2. 并发处理演示
            concurrent_results = await self.demo_concurrent_processing()
            
            # 3. 批处理优化演示
            batch_results = await self.demo_batch_processing()
            
            # 4. 性能监控演示
            monitoring_results = await self.demo_performance_monitoring()
            
            # 生成演示总结
            await self.generate_demo_summary({
                "cache_optimization": cache_results,
                "concurrent_processing": concurrent_results,
                "batch_processing": batch_results,
                "performance_monitoring": monitoring_results
            })
            
        except Exception as e:
            print(f"❌ 演示过程中发生错误: {e}")
            raise
        finally:
            if self.manager:
                await self.manager.close()
    
    async def generate_demo_summary(self, demo_data: Dict[str, Any]):
        """生成演示总结"""
        print(f"\n🎊 性能优化演示总结")
        print("=" * 80)
        
        cache_data = demo_data["cache_optimization"]
        concurrent_data = demo_data["concurrent_processing"]
        batch_data = demo_data["batch_processing"]
        
        print(f"✅ 缓存优化效果:")
        print(f"  🚀 查询加速: {cache_data['speedup']:.1f}x")
        print(f"  ⏱️  时间节省: {cache_data['time_saved_percent']:.1f}%")
        print(f"  💾 缓存命中显著提升查询性能")
        
        print(f"\n✅ 并发处理能力:")
        baseline_throughput = concurrent_data[1]["throughput"]
        max_throughput = max(r["throughput"] for r in concurrent_data.values())
        optimal_level = max(concurrent_data.keys(), key=lambda k: concurrent_data[k]["throughput"])
        print(f"  📈 最大吞吐量: {max_throughput:.1f} 请求/秒")
        print(f"  🔢 最优并发级别: {optimal_level}")
        print(f"  ⚡ 并发提升: {max_throughput / baseline_throughput:.1f}x")
        
        print(f"\n✅ 批处理优化:")
        print(f"  📦 批处理加速: {batch_data['speedup']:.1f}x")
        print(f"  📊 效率提升: {((batch_data['individual_time'] - batch_data['batch_time']) / batch_data['individual_time'] * 100):.1f}%")
        print(f"  🔧 批量操作显著减少数据库开销")
        
        print(f"\n🎯 核心优化特性:")
        print(f"  🏊‍♂️ 连接池管理: 自动调节数据库连接，支持高并发")
        print(f"  💾 智能缓存: LRU策略，自动过期清理，显著提升查询速度")
        print(f"  📦 批处理优化: 减少数据库I/O，提升写入性能")
        print(f"  📊 实时监控: 性能指标追踪，健康状态检查")
        print(f"  🔧 自动优化: 根据负载自动调整系统参数")
        
        print(f"\n💡 实际应用场景:")
        print(f"  🏢 企业级部署: 支持多用户并发访问")
        print(f"  🌐 大规模记忆搜索: 快速响应跨项目查询")
        print(f"  📈 高负载环境: 自动扩展处理能力")
        print(f"  🔄 持续运行: 7x24小时稳定服务")
        
        print(f"\n🔧 技术亮点:")
        print(f"  ⚡ 异步I/O: 非阻塞数据库操作")
        print(f"  🔗 连接复用: WAL模式SQLite优化")
        print(f"  🧠 智能缓存: 自适应TTL和LRU策略")
        print(f"  📊 性能监控: 实时指标收集和分析")
        print(f"  🛡️  容错处理: 优雅降级和错误恢复")


async def main():
    """主函数"""
    demo = PerformanceOptimizationDemo()
    
    try:
        await demo.run_complete_demo()
        print(f"\n🎉 Claude Memory MCP 性能优化演示完成！")
        
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())