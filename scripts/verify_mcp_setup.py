#!/usr/bin/env python3
"""
最终MCP设置验证
确认所有配置正确并提供重启指导
"""

import json
from pathlib import Path

def verify_complete_setup():
    """验证完整的MCP设置"""
    
    claude_config_path = Path.home() / ".claude.json"
    project_path = "/home/jetgogoing/claude_memory"
    
    print("🔍 完整MCP设置验证")
    print("=" * 50)
    
    # 1. 验证文件存在
    files_to_check = [
        ("/home/jetgogoing/claude_memory/venv-claude-memory/bin/python", "Python虚拟环境"),
        ("/home/jetgogoing/claude_memory/simple_mcp_server.py", "MCP服务器脚本"),
        (str(claude_config_path), "Claude配置文件")
    ]
    
    print("📁 文件检查:")
    all_files_exist = True
    for file_path, description in files_to_check:
        if Path(file_path).exists():
            print(f"✅ {description}: {file_path}")
        else:
            print(f"❌ {description}: {file_path} - 不存在")
            all_files_exist = False
    
    if not all_files_exist:
        return False
    
    # 2. 验证JSON配置
    print("\n⚙️ 配置验证:")
    try:
        with open(claude_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ Claude配置文件JSON格式正确")
    except Exception as e:
        print(f"❌ Claude配置文件错误: {e}")
        return False
    
    # 3. 验证项目配置
    if project_path not in config.get("projects", {}):
        print(f"❌ 项目 {project_path} 不在配置中")
        return False
    
    project_config = config["projects"][project_path]
    
    # 检查MCP服务器配置
    mcp_servers = project_config.get("mcpServers", {})
    if "claude-memory-mcp" not in mcp_servers:
        print("❌ 项目级缺少claude-memory-mcp配置")
        return False
    
    mcp_config = mcp_servers["claude-memory-mcp"]
    expected_command = "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python"
    expected_script = "/home/jetgogoing/claude_memory/simple_mcp_server.py"
    
    if mcp_config.get("command") != expected_command:
        print(f"❌ Python命令路径错误: {mcp_config.get('command')}")
        return False
    
    if expected_script not in mcp_config.get("args", []):
        print(f"❌ 脚本路径错误: {mcp_config.get('args')}")
        return False
    
    print("✅ 项目级MCP服务器配置正确")
    
    # 检查启用状态
    enabled_servers = project_config.get("enabledMcpjsonServers", [])
    if "claude-memory-mcp" not in enabled_servers:
        print("❌ claude-memory-mcp未在启用列表中")
        return False
    
    print("✅ MCP服务已启用")
    
    # 4. 验证全局配置
    global_mcp = config.get("mcpServers", {})
    if "claude-memory-mcp" in global_mcp:
        print("✅ 全局MCP配置存在")
    else:
        print("⚠️ 全局MCP配置缺失（项目级配置足够）")
    
    print("\n🎊 所有验证通过！")
    
    # 提供重启指导
    print("\n📋 下一步操作:")
    print("1. 完全退出当前Claude CLI会话")
    print("2. 重新启动Claude CLI: claude")
    print("3. 在新会话中输入: /mcp")
    print("4. 查看claude-memory-mcp服务状态")
    print("5. 测试MCP工具:")
    print("   /mcp claude-memory-mcp get_service_status")
    print("   /mcp claude-memory-mcp search_memories '测试查询'")
    
    print("\n🚀 Claude Memory MCP服务配置完成！")
    return True

if __name__ == "__main__":
    verify_complete_setup()