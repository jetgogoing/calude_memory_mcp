#!/usr/bin/env python3
"""
MCP服务诊断脚本
"""

import subprocess
import sys
import json
from pathlib import Path

def test_python_environment():
    """测试Python环境"""
    print("🔍 测试Python环境...")
    
    # 检查虚拟环境
    venv_python = "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python"
    
    try:
        result = subprocess.run([venv_python, "--version"], 
                              capture_output=True, text=True, timeout=5)
        print(f"✅ Python版本: {result.stdout.strip()}")
    except Exception as e:
        print(f"❌ Python检查失败: {e}")
        return False
    
    # 检查MCP模块
    try:
        result = subprocess.run([venv_python, "-c", "from mcp.server import Server; print('MCP OK')"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ MCP模块正常")
        else:
            print(f"❌ MCP模块错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ MCP模块检查失败: {e}")
        return False
    
    return True

def test_mcp_script():
    """测试MCP脚本"""
    print("\n🔍 测试MCP脚本...")
    
    script_path = "/home/jetgogoing/claude_memory/minimal_mcp_server.py"
    venv_python = "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python"
    
    # 检查文件存在
    if not Path(script_path).exists():
        print(f"❌ 脚本文件不存在: {script_path}")
        return False
    
    print(f"✅ 脚本文件存在: {script_path}")
    
    # 测试导入
    try:
        result = subprocess.run([venv_python, "-c", f"exec(open('{script_path}').read())"], 
                              capture_output=True, text=True, timeout=3)
        if result.returncode != 0:
            print(f"❌ 脚本导入失败: {result.stderr}")
            return False
        else:
            print("✅ 脚本可以导入")
    except subprocess.TimeoutExpired:
        print("✅ 脚本正常启动(超时表示等待输入)")
    except Exception as e:
        print(f"❌ 脚本测试失败: {e}")
        return False
    
    return True

def check_claude_config():
    """检查Claude配置"""
    print("\n🔍 检查Claude配置...")
    
    config_path = Path.home() / ".claude.json"
    
    if not config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        mcp_servers = config.get("mcpServers", {})
        claude_memory = mcp_servers.get("claude-memory")
        
        if not claude_memory:
            print("❌ claude-memory MCP配置不存在")
            return False
        
        print("✅ claude-memory MCP配置存在")
        print(f"   命令: {claude_memory.get('command')}")
        print(f"   参数: {claude_memory.get('args')}")
        
        # 检查命令和文件是否存在
        command = claude_memory.get('command')
        args = claude_memory.get('args', [])
        
        if not Path(command).exists():
            print(f"❌ Python解释器不存在: {command}")
            return False
        
        if args and not Path(args[0]).exists():
            print(f"❌ MCP脚本不存在: {args[0]}")
            return False
        
        print("✅ 所有文件路径都存在")
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False
    
    return True

def main():
    print("🚀 Claude Memory MCP 服务诊断")
    print("=" * 50)
    
    all_ok = True
    
    # 测试步骤
    steps = [
        test_python_environment,
        test_mcp_script,
        check_claude_config
    ]
    
    for step in steps:
        if not step():
            all_ok = False
            print("⚠️  检测到问题，请检查上述错误")
            break
    
    if all_ok:
        print("\n🎉 所有检查通过！")
        print("\n📋 下一步:")
        print("1. 重启Claude CLI")
        print("2. 使用 /mcp 查看服务状态")
        print("3. 测试工具: /mcp claude-memory test_connection")
    else:
        print("\n❌ 诊断发现问题，请修复后重试")

if __name__ == "__main__":
    main()