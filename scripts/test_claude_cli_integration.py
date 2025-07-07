#!/usr/bin/env python3
"""
Claude CLI集成测试脚本
验证Claude CLI与Claude Memory MCP服务的连接
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def test_claude_cli_mcp_config():
    """测试Claude CLI MCP配置"""
    print("🔍 Claude CLI MCP配置测试")
    print("=" * 50)
    
    # 检查Claude CLI是否安装
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Claude CLI未安装或不在PATH中")
            print("请先安装Claude CLI: https://docs.anthropic.com/claude/docs/claude-cli")
            return False
        else:
            print(f"✅ Claude CLI版本: {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("❌ Claude CLI响应超时")
        return False
    except FileNotFoundError:
        print("❌ Claude CLI未找到")
        return False
    
    # 检查MCP配置文件
    mcp_config_paths = [
        Path.home() / ".claude" / "mcp_servers.json",
        Path.home() / ".config" / "claude" / "mcp_servers.json"
    ]
    
    config_found = False
    for config_path in mcp_config_paths:
        if config_path.exists():
            print(f"✅ 找到MCP配置文件: {config_path}")
            
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "claude-memory-mcp" in config:
                    print("✅ Claude Memory MCP配置存在")
                    print(f"   命令: {config['claude-memory-mcp']['command']}")
                    print(f"   参数: {' '.join(config['claude-memory-mcp']['args'])}")
                    print(f"   工作目录: {config['claude-memory-mcp']['cwd']}")
                    config_found = True
                else:
                    print("❌ Claude Memory MCP配置未找到")
                    
            except json.JSONDecodeError:
                print(f"❌ MCP配置文件格式错误: {config_path}")
            break
    
    if not config_found:
        print("❌ 未找到有效的MCP配置")
        return False
    
    return True

def test_mcp_service_startup():
    """测试MCP服务启动"""
    print("\n🚀 MCP服务启动测试")
    print("=" * 50)
    
    project_root = Path(__file__).parent.parent
    
    try:
        # 启动MCP服务进行快速测试
        cmd = [
            "python", "-m", "claude_memory", "--mode", "config-check"
        ]
        
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                "PYTHONPATH": str(project_root / "src"),
                "PATH": str(Path.home() / "claude_memory" / "venv-claude-memory" / "bin") + ":" + subprocess.os.environ.get("PATH", "")
            }
        )
        
        if result.returncode == 0:
            print("✅ MCP服务配置检查通过")
            return True
        else:
            print(f"❌ MCP服务配置检查失败:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ MCP服务启动超时")
        return False
    except Exception as e:
        print(f"❌ MCP服务启动测试失败: {e}")
        return False

def test_qdrant_connection():
    """测试Qdrant连接"""
    print("\n🔍 Qdrant连接测试")
    print("=" * 50)
    
    try:
        import httpx
        
        # 测试Qdrant健康检查
        with httpx.Client() as client:
            response = client.get("http://localhost:6333/", timeout=5.0)
            
            if response.status_code == 200:
                print("✅ Qdrant服务运行正常")
                
                # 获取集合信息
                collections_response = client.get("http://localhost:6333/collections")
                if collections_response.status_code == 200:
                    collections = collections_response.json()["result"]["collections"]
                    print(f"✅ 发现{len(collections)}个Qdrant集合")
                    
                    for collection in collections:
                        print(f"   📦 {collection['name']}")
                else:
                    print("⚠️  无法获取Qdrant集合信息")
                
                return True
            else:
                print(f"❌ Qdrant健康检查失败: {response.status_code}")
                return False
                
    except ImportError:
        print("❌ 缺少httpx依赖，无法测试Qdrant连接")
        return False
    except Exception as e:
        print(f"❌ Qdrant连接测试失败: {e}")
        return False

def show_integration_guide():
    """显示集成指南"""
    print("\n📋 Claude CLI集成指南")
    print("=" * 50)
    print("1. 启动所需服务:")
    print("   bash scripts/start_qdrant.sh")
    print()
    print("2. 测试MCP服务:")
    print("   source venv-claude-memory/bin/activate")
    print("   python -m claude_memory --mode config-check")
    print()
    print("3. 启动Claude CLI并测试MCP集成:")
    print("   claude --mcp")
    print()
    print("4. 在Claude CLI中测试记忆功能:")
    print("   # 搜索记忆")
    print("   /mcp claude-memory-mcp search_memories '测试查询'")
    print()
    print("   # 获取服务状态")
    print("   /mcp claude-memory-mcp get_service_status")
    print()
    print("5. 如果遇到问题:")
    print("   - 检查Qdrant服务是否运行: curl http://localhost:6333/health")
    print("   - 检查虚拟环境是否激活")
    print("   - 检查API密钥是否配置正确")
    print("   - 查看日志文件: logs/claude_memory.log")

def main():
    """主测试流程"""
    print("🧪 Claude CLI集成测试")
    print("🎯 验证Claude Memory MCP服务与Claude CLI的集成")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    # 测试1: Claude CLI MCP配置
    if test_claude_cli_mcp_config():
        tests_passed += 1
    
    # 测试2: MCP服务启动
    if test_mcp_service_startup():
        tests_passed += 1
    
    # 测试3: Qdrant连接
    if test_qdrant_connection():
        tests_passed += 1
    
    # 显示结果
    print(f"\n📊 测试结果: {tests_passed}/{total_tests} 通过")
    
    if tests_passed == total_tests:
        print("🎉 所有集成测试通过！Claude CLI已准备就绪")
        print("🚀 可以开始使用Claude Memory MCP服务")
    else:
        print("⚠️  部分测试未通过，请检查配置")
        show_integration_guide()
    
    return tests_passed == total_tests

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🚫 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试执行失败: {e}")
        sys.exit(1)