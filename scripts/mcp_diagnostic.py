#!/usr/bin/env python3
"""
Claude Memory MCP诊断工具
检查MCP服务配置和Claude CLI集成问题
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def check_file_exists(path, description):
    """检查文件是否存在"""
    exists = Path(path).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {path}")
    return exists

def check_python_executable(python_path):
    """检查Python可执行文件"""
    try:
        result = subprocess.run([python_path, "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Python可执行: {python_path} ({result.stdout.strip()})")
            return True
        else:
            print(f"❌ Python不可执行: {python_path}")
            return False
    except Exception as e:
        print(f"❌ Python执行错误: {python_path} - {e}")
        return False

def check_mcp_server_syntax(server_path):
    """检查MCP服务器语法"""
    try:
        result = subprocess.run([sys.executable, "-m", "py_compile", server_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ MCP服务器语法正确: {server_path}")
            return True
        else:
            print(f"❌ MCP服务器语法错误: {server_path}")
            print(f"   错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 语法检查失败: {e}")
        return False

def test_mcp_import(python_path, server_path):
    """测试MCP服务器导入"""
    try:
        test_script = f"""
import sys
sys.path.insert(0, '{Path(server_path).parent / "src"}')
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    print("MCP导入成功")
    sys.exit(0)
except ImportError as e:
    print(f"MCP导入失败: {{e}}")
    sys.exit(1)
"""
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ MCP模块导入成功")
            return True
        else:
            print(f"❌ MCP模块导入失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        return False

def main():
    print("🔍 Claude Memory MCP诊断工具")
    print("=" * 50)
    
    # 检查配置文件路径
    home_dir = Path.home()
    claude_config_dir = home_dir / ".claude"
    mcp_config_file = claude_config_dir / "mcp_servers.json"
    
    print("\n📂 配置文件检查:")
    check_file_exists(claude_config_dir, "Claude配置目录")
    config_exists = check_file_exists(mcp_config_file, "MCP配置文件")
    
    if not config_exists:
        print("❌ 关键问题：MCP配置文件不存在！")
        print(f"   请确保 {mcp_config_file} 存在")
        return False
    
    # 读取并验证MCP配置
    print("\n⚙️ MCP配置验证:")
    try:
        with open(mcp_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if 'claude-memory-mcp' not in config:
            print("❌ 配置中未找到 'claude-memory-mcp' 服务")
            return False
        
        mcp_config = config['claude-memory-mcp']
        print(f"✅ 找到MCP服务配置")
        
        # 检查命令路径
        python_path = mcp_config.get('command')
        if not python_path:
            print("❌ 配置中缺少 'command' 字段")
            return False
        
        # 检查参数
        args = mcp_config.get('args', [])
        if not args:
            print("❌ 配置中缺少 'args' 字段")
            return False
        
        server_path = args[0] if args else None
        if not server_path:
            print("❌ 未指定MCP服务器脚本路径")
            return False
        
        print(f"📄 Python命令: {python_path}")
        print(f"📄 服务器脚本: {server_path}")
        print(f"📄 工作目录: {mcp_config.get('cwd', '未指定')}")
        
    except Exception as e:
        print(f"❌ 配置文件读取错误: {e}")
        return False
    
    # 检查文件存在性
    print("\n📁 文件存在性检查:")
    python_exists = check_file_exists(python_path, "Python可执行文件")
    server_exists = check_file_exists(server_path, "MCP服务器脚本")
    
    if not python_exists or not server_exists:
        print("❌ 关键文件缺失！")
        return False
    
    # 检查Python可执行性
    print("\n🐍 Python环境检查:")
    python_ok = check_python_executable(python_path)
    
    # 检查MCP服务器语法
    print("\n📜 服务器脚本检查:")
    syntax_ok = check_mcp_server_syntax(server_path)
    
    # 测试MCP模块导入
    print("\n📦 依赖模块检查:")
    import_ok = test_mcp_import(python_path, server_path)
    
    # 总结
    print("\n" + "=" * 50)
    if all([config_exists, python_ok, syntax_ok, import_ok]):
        print("🎉 所有检查通过！MCP配置看起来正确。")
        print("\n💡 如果Claude CLI仍然无法识别服务，请尝试：")
        print("   1. 完全重启Claude CLI")
        print("   2. 检查Claude CLI是否支持MCP功能")
        print("   3. 查看Claude CLI启动日志")
        return True
    else:
        print("❌ 发现配置问题，需要修复上述错误。")
        return False

if __name__ == "__main__":
    main()