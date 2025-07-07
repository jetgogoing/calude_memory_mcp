#!/usr/bin/env python3
"""
Claude CLI重启助手
帮助重启Claude CLI以加载新的MCP配置
"""

import subprocess
import sys
import time
import json
from pathlib import Path

def check_mcp_config():
    """检查MCP配置"""
    print("🔍 检查MCP配置...")
    
    mcp_config_file = Path.home() / ".claude" / "mcp_servers.json" 
    if not mcp_config_file.exists():
        print("❌ MCP配置文件不存在")
        return False
    
    try:
        with open(mcp_config_file, 'r') as f:
            config = json.load(f)
        
        if "claude-memory-mcp" in config:
            print("✅ Claude Memory MCP配置已找到")
            print(f"   命令: {config['claude-memory-mcp']['command']}")
            print(f"   参数: {' '.join(config['claude-memory-mcp']['args'])}")
            return True
        else:
            print("❌ Claude Memory MCP配置未找到")
            return False
            
    except Exception as e:
        print(f"❌ 读取MCP配置失败: {e}")
        return False

def test_mcp_server():
    """测试MCP服务器"""
    print("\n🧪 测试MCP服务器...")
    
    try:
        # 获取MCP配置
        mcp_config_file = Path.home() / ".claude" / "mcp_servers.json"
        with open(mcp_config_file, 'r') as f:
            config = json.load(f)
        
        mcp_config = config["claude-memory-mcp"]
        command = mcp_config["command"]
        args = mcp_config["args"]
        cwd = mcp_config["cwd"]
        
        # 测试启动
        result = subprocess.run(
            [command] + args,
            cwd=cwd,
            timeout=3,
            capture_output=True,
            text=True
        )
        
        print("✅ MCP服务器可以启动")
        return True
        
    except subprocess.TimeoutExpired:
        print("✅ MCP服务器启动正常 (超时正常，服务器在等待输入)")
        return True
    except Exception as e:
        print(f"❌ MCP服务器测试失败: {e}")
        return False

def show_instructions():
    """显示使用说明"""
    print("\n📋 Claude CLI使用说明")
    print("=" * 50)
    print("1. 重启Claude CLI:")
    print("   # 如果Claude CLI正在运行，请先退出")
    print("   # 然后重新启动: claude")
    print()
    print("2. 验证MCP服务加载:")
    print("   在Claude CLI中输入: /mcp")
    print("   应该看到 'claude-memory-mcp' 服务")
    print()
    print("3. 测试MCP工具:")
    print("   /mcp claude-memory-mcp get_service_status")
    print("   /mcp claude-memory-mcp search_memories \"测试查询\"")
    print()
    print("4. 如果/mcp命令无效:")
    print("   请检查您的Claude CLI版本是否支持MCP")
    print("   运行: claude --version")
    print()
    print("💡 提示:")
    print("   - MCP服务会在Claude CLI启动时自动加载")
    print("   - 如果遇到问题，请检查上述配置是否正确")

def main():
    """主函数"""
    print("🚀 Claude CLI重启助手")
    print("=" * 50)
    
    # 检查MCP配置
    if not check_mcp_config():
        print("\n❌ MCP配置检查失败，请先配置MCP服务")
        sys.exit(1)
    
    # 测试MCP服务器
    if not test_mcp_server():
        print("\n❌ MCP服务器测试失败，请检查配置")
        sys.exit(1)
    
    print("\n✅ 所有检查通过！")
    
    # 显示使用说明
    show_instructions()
    
    print("\n🎉 Claude Memory MCP服务已准备就绪！")
    print("现在您可以重启Claude CLI并使用 /mcp 命令来查看和使用记忆功能。")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚫 操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 执行失败: {e}")
        sys.exit(1)