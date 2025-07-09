#!/usr/bin/env python3
"""
Claude Memory MCP服务 - 预部署检查脚本

在部署前执行完整的环境和配置检查，确保所有依赖项都已就绪。
"""

import asyncio
import os
import sys
import psutil
import socket
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from claude_memory.config.settings import get_settings
from claude_memory.database.session_manager import get_db_session
from claude_memory.utils.model_manager import ModelManager
import httpx
from sqlalchemy import text
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

# 配置日志
logger = structlog.get_logger(__name__)


class PreDeploymentChecker:
    """预部署检查器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.check_results: Dict[str, Dict] = {}
        self.has_errors = False
        self.has_warnings = False
        
    async def run_all_checks(self) -> bool:
        """
        运行所有检查
        
        Returns:
            bool: 是否通过所有检查
        """
        print("\n🔍 Claude Memory MCP服务 - 预部署检查")
        print("=" * 60)
        print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"项目路径: {project_root}")
        print("=" * 60)
        
        # 执行各项检查
        await self.check_environment_variables()
        await self.check_database_connectivity()
        await self.check_qdrant_connectivity()
        await self.check_api_keys()
        await self.check_model_access()
        await self.check_vector_dimensions()
        await self.check_ports_availability()
        await self.check_file_permissions()
        await self.check_system_resources()
        await self.check_dependencies()
        
        # 输出总结
        self.print_summary()
        
        return not self.has_errors
    
    async def check_environment_variables(self):
        """检查环境变量"""
        print("\n📋 检查环境变量...")
        
        required_vars = {
            'SILICONFLOW_API_KEY': '必需',
            'DATABASE_URL': '可选（有默认值）',
            'QDRANT_URL': '可选（有默认值）',
            'GEMINI_API_KEY': '可选',
            'OPENROUTER_API_KEY': '可选',
        }
        
        results = {}
        for var, requirement in required_vars.items():
            value = os.getenv(var)
            if value:
                # 隐藏敏感信息
                display_value = f"{value[:8]}..." if 'KEY' in var else value
                results[var] = {'status': '✅', 'value': display_value}
            else:
                if requirement == '必需':
                    results[var] = {'status': '❌', 'value': '未设置'}
                    self.has_errors = True
                else:
                    results[var] = {'status': '⚠️', 'value': '未设置（使用默认值）'}
                    self.has_warnings = True
        
        self.check_results['environment_variables'] = results
        
        # 打印结果
        for var, result in results.items():
            print(f"  {result['status']} {var}: {result['value']}")
    
    async def check_database_connectivity(self):
        """检查数据库连接"""
        print("\n🗄️ 检查PostgreSQL数据库连接...")
        
        try:
            async with get_db_session() as session:
                # 测试基本连接
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                
                # 检查必要的表
                table_check = await session.execute(
                    text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('conversations', 'messages', 'memory_units')
                        ORDER BY table_name
                    """)
                )
                existing_tables = [row[0] for row in table_check]
                
                self.check_results['database'] = {
                    'status': '✅',
                    'version': version,
                    'tables': existing_tables,
                    'missing_tables': list(set(['conversations', 'messages', 'memory_units']) - set(existing_tables))
                }
                
                print(f"  ✅ 数据库连接成功")
                print(f"  📊 PostgreSQL版本: {version.split(',')[0]}")
                print(f"  📋 已存在的表: {', '.join(existing_tables)}")
                
                if self.check_results['database']['missing_tables']:
                    print(f"  ⚠️ 缺少的表: {', '.join(self.check_results['database']['missing_tables'])}")
                    self.has_warnings = True
                    
        except Exception as e:
            self.check_results['database'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_errors = True
            print(f"  ❌ 数据库连接失败: {str(e)}")
    
    async def check_qdrant_connectivity(self):
        """检查Qdrant向量数据库连接"""
        print("\n🔍 检查Qdrant向量数据库连接...")
        
        try:
            client = QdrantClient(url=self.settings.qdrant.qdrant_url)
            
            # 获取集合信息
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            # 检查所需的集合
            required_collection = self.settings.qdrant.collection_name
            collection_exists = required_collection in collection_names
            
            self.check_results['qdrant'] = {
                'status': '✅',
                'collections': collection_names,
                'required_collection': required_collection,
                'collection_exists': collection_exists
            }
            
            print(f"  ✅ Qdrant连接成功")
            print(f"  📊 现有集合: {', '.join(collection_names) if collection_names else '无'}")
            
            if collection_exists:
                # 获取集合详情
                collection_info = client.get_collection(required_collection)
                print(f"  ✅ 所需集合 '{required_collection}' 已存在")
                print(f"  📏 向量维度: {collection_info.config.params.vectors.size}")
                print(f"  📐 距离度量: {collection_info.config.params.vectors.distance}")
            else:
                print(f"  ⚠️ 所需集合 '{required_collection}' 不存在（将在启动时创建）")
                self.has_warnings = True
                
        except Exception as e:
            self.check_results['qdrant'] = {
                'status': '❌',
                'error': str(e)
            }
            self.has_errors = True
            print(f"  ❌ Qdrant连接失败: {str(e)}")
    
    async def check_api_keys(self):
        """检查API密钥有效性"""
        print("\n🔑 检查API密钥有效性...")
        
        results = {}
        
        # 检查SiliconFlow API
        if self.settings.models.siliconflow_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.settings.models.siliconflow_base_url}/models",
                        headers={"Authorization": f"Bearer {self.settings.models.siliconflow_api_key}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        results['siliconflow'] = {'status': '✅', 'message': 'API密钥有效'}
                    else:
                        results['siliconflow'] = {'status': '❌', 'message': f'HTTP {response.status_code}'}
                        self.has_errors = True
            except Exception as e:
                results['siliconflow'] = {'status': '❌', 'message': str(e)}
                self.has_errors = True
        else:
            results['siliconflow'] = {'status': '⚠️', 'message': '未配置'}
            self.has_warnings = True
        
        # 检查Gemini API（如果配置）
        if self.settings.models.gemini_api_key:
            try:
                # 简单验证密钥格式
                if len(self.settings.models.gemini_api_key) > 30:
                    results['gemini'] = {'status': '✅', 'message': 'API密钥格式正确'}
                else:
                    results['gemini'] = {'status': '❌', 'message': 'API密钥格式错误'}
                    self.has_errors = True
            except Exception as e:
                results['gemini'] = {'status': '❌', 'message': str(e)}
                self.has_errors = True
        else:
            results['gemini'] = {'status': '⚠️', 'message': '未配置（可选）'}
        
        self.check_results['api_keys'] = results
        
        # 打印结果
        for api, result in results.items():
            print(f"  {result['status']} {api.upper()}: {result['message']}")
    
    async def check_model_access(self):
        """检查模型访问"""
        print("\n🤖 检查模型访问...")
        
        model_manager = ModelManager()
        results = {}
        
        # 测试嵌入模型
        try:
            test_text = "测试文本"
            embedding = await model_manager.get_embedding(test_text)
            if embedding and len(embedding) > 0:
                results['embedding'] = {
                    'status': '✅',
                    'model': self.settings.models.default_embedding_model,
                    'dimensions': len(embedding)
                }
                print(f"  ✅ 嵌入模型: {self.settings.models.default_embedding_model} (维度: {len(embedding)})")
            else:
                results['embedding'] = {'status': '❌', 'error': '返回空嵌入'}
                self.has_errors = True
                print(f"  ❌ 嵌入模型测试失败")
        except Exception as e:
            results['embedding'] = {'status': '❌', 'error': str(e)}
            self.has_errors = True
            print(f"  ❌ 嵌入模型访问失败: {str(e)}")
        
        self.check_results['models'] = results
    
    async def check_vector_dimensions(self):
        """检查向量维度配置"""
        print("\n📐 检查向量维度配置...")
        
        configured_size = self.settings.qdrant.vector_size
        print(f"  📏 配置的向量维度: {configured_size}")
        
        # 如果Qdrant集合已存在，检查维度是否匹配
        if 'qdrant' in self.check_results and self.check_results['qdrant'].get('collection_exists'):
            try:
                client = QdrantClient(url=self.settings.qdrant.qdrant_url)
                collection_info = client.get_collection(self.settings.qdrant.collection_name)
                actual_size = collection_info.config.params.vectors.size
                
                if actual_size != configured_size:
                    print(f"  ⚠️ 警告: Qdrant集合维度({actual_size})与配置({configured_size})不匹配")
                    self.has_warnings = True
                else:
                    print(f"  ✅ 向量维度匹配")
                    
            except Exception as e:
                print(f"  ❌ 无法验证向量维度: {str(e)}")
    
    async def check_ports_availability(self):
        """检查端口可用性"""
        print("\n🔌 检查端口可用性...")
        
        ports_to_check = [
            (self.settings.port, 'MCP服务'),
            (5432, 'PostgreSQL'),
            (6333, 'Qdrant HTTP'),
            (6334, 'Qdrant gRPC'),
        ]
        
        results = {}
        for port, service in ports_to_check:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # 尝试连接到端口
                result = sock.connect_ex(('localhost', port))
                if result == 0:
                    # 端口被占用（服务可能已在运行）
                    results[f"{service}:{port}"] = {'status': '✅', 'state': '已占用（服务运行中）'}
                    print(f"  ✅ {service} (端口 {port}): 已占用（服务运行中）")
                else:
                    # 端口空闲
                    results[f"{service}:{port}"] = {'status': '⚠️', 'state': '空闲（服务未运行）'}
                    print(f"  ⚠️ {service} (端口 {port}): 空闲（服务未运行）")
                    if service in ['PostgreSQL', 'Qdrant HTTP']:
                        self.has_warnings = True
            finally:
                sock.close()
        
        self.check_results['ports'] = results
    
    async def check_file_permissions(self):
        """检查文件权限"""
        print("\n📁 检查文件权限...")
        
        paths_to_check = [
            (project_root / 'logs', '日志目录', True),
            (project_root / 'data', '数据目录', True),
            (project_root / '.env', '环境配置文件', False),
            (project_root / 'scripts', '脚本目录', False),
        ]
        
        results = {}
        for path, description, need_write in paths_to_check:
            if path.exists():
                readable = os.access(path, os.R_OK)
                writable = os.access(path, os.W_OK)
                
                if readable and (not need_write or writable):
                    results[str(path)] = {'status': '✅', 'permissions': 'rw' if writable else 'r'}
                    print(f"  ✅ {description}: {'可读写' if writable else '只读'}")
                else:
                    results[str(path)] = {'status': '❌', 'permissions': 'insufficient'}
                    self.has_errors = True
                    print(f"  ❌ {description}: 权限不足")
            else:
                if need_write:
                    # 尝试创建目录
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        results[str(path)] = {'status': '✅', 'permissions': 'created'}
                        print(f"  ✅ {description}: 已创建")
                    except Exception as e:
                        results[str(path)] = {'status': '❌', 'error': str(e)}
                        self.has_errors = True
                        print(f"  ❌ {description}: 创建失败 - {str(e)}")
                else:
                    results[str(path)] = {'status': '⚠️', 'permissions': 'not_found'}
                    print(f"  ⚠️ {description}: 不存在")
                    if description == '环境配置文件':
                        self.has_warnings = True
        
        self.check_results['file_permissions'] = results
    
    async def check_system_resources(self):
        """检查系统资源"""
        print("\n💻 检查系统资源...")
        
        # CPU信息
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_available_gb = memory.available / (1024**3)
        memory_percent = memory.percent
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        disk_available_gb = disk.free / (1024**3)
        disk_percent = disk.percent
        
        resources = {
            'cpu': {
                'cores': cpu_count,
                'usage': f"{cpu_percent}%",
                'status': '✅' if cpu_percent < 80 else '⚠️'
            },
            'memory': {
                'available': f"{memory_available_gb:.1f} GB",
                'usage': f"{memory_percent}%",
                'status': '✅' if memory_available_gb > 2 else '⚠️'
            },
            'disk': {
                'available': f"{disk_available_gb:.1f} GB",
                'usage': f"{disk_percent}%",
                'status': '✅' if disk_available_gb > 5 else '⚠️'
            }
        }
        
        self.check_results['system_resources'] = resources
        
        # 打印结果
        print(f"  {resources['cpu']['status']} CPU: {resources['cpu']['cores']} 核心, 使用率 {resources['cpu']['usage']}")
        print(f"  {resources['memory']['status']} 内存: {resources['memory']['available']} 可用, 使用率 {resources['memory']['usage']}")
        print(f"  {resources['disk']['status']} 磁盘: {resources['disk']['available']} 可用, 使用率 {resources['disk']['usage']}")
        
        # 检查资源是否充足
        if memory_available_gb < 2:
            print("  ⚠️ 警告: 可用内存较少，建议至少保留2GB")
            self.has_warnings = True
        if disk_available_gb < 5:
            print("  ⚠️ 警告: 可用磁盘空间较少，建议至少保留5GB")
            self.has_warnings = True
    
    async def check_dependencies(self):
        """检查Python依赖"""
        print("\n📦 检查Python依赖...")
        
        critical_packages = [
            'sqlalchemy',
            'qdrant-client',
            'pydantic',
            'structlog',
            'httpx',
            'psutil',
            'tenacity',
        ]
        
        results = {}
        import importlib
        
        for package in critical_packages:
            try:
                module = importlib.import_module(package.replace('-', '_'))
                version = getattr(module, '__version__', 'unknown')
                results[package] = {'status': '✅', 'version': version}
                print(f"  ✅ {package}: {version}")
            except ImportError:
                results[package] = {'status': '❌', 'version': 'not installed'}
                self.has_errors = True
                print(f"  ❌ {package}: 未安装")
        
        self.check_results['dependencies'] = results
    
    def print_summary(self):
        """打印检查总结"""
        print("\n" + "=" * 60)
        print("📊 检查总结")
        print("=" * 60)
        
        if self.has_errors:
            print("❌ 发现严重问题，请修复后再部署")
        elif self.has_warnings:
            print("⚠️ 发现警告，建议检查但可以继续部署")
        else:
            print("✅ 所有检查通过，可以安全部署")
        
        # 保存检查结果到文件
        report_path = project_root / 'logs' / f'pre_deploy_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'has_errors': self.has_errors,
                'has_warnings': self.has_warnings,
                'results': self.check_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存到: {report_path}")


async def main():
    """主函数"""
    checker = PreDeploymentChecker()
    success = await checker.run_all_checks()
    
    # 返回适当的退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())