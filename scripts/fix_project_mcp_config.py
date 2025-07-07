#!/usr/bin/env python3
"""
修复项目级MCP配置
确保claude-memory-mcp服务正确配置在项目级别
"""

import json
from pathlib import Path

def fix_project_mcp_config():
    """修复项目级MCP配置"""
    
    claude_config_path = Path.home() / ".claude.json"
    project_path = "/home/jetgogoing/claude_memory"
    
    # 读取配置
    with open(claude_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 确保项目存在
    if project_path not in config.get("projects", {}):
        print(f"❌ 项目 {project_path} 不存在于配置中")
        return False
    
    project_config = config["projects"][project_path]
    
    # MCP服务器配置
    mcp_config = {
        "claude-memory-mcp": {
            "type": "stdio",
            "command": "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
            "args": [
                "/home/jetgogoing/claude_memory/simple_mcp_server.py"
            ],
            "env": {
                "QDRANT_URL": "http://localhost:6333",
                "QDRANT_API_KEY": "",
                "SILICONFLOW_API_KEY": "sk-tjjznxtevmlynypmydlhqepnatclvlrimsygimtyafdoxklw",
                "GEMINI_API_KEY": "AIzaSyDTBboAMDzVY7UMKK5gbNhwKufNTSDY0sw",
                "OPENROUTER_API_KEY": "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"
            }
        }
    }
    
    print("🔧 修复项目级MCP配置...")
    
    # 更新项目级MCP配置
    project_config["mcpServers"] = mcp_config
    
    # 确保服务在启用列表中
    if "enabledMcpjsonServers" not in project_config:
        project_config["enabledMcpjsonServers"] = []
    
    if "claude-memory-mcp" not in project_config["enabledMcpjsonServers"]:
        project_config["enabledMcpjsonServers"].append("claude-memory-mcp")
    
    # 确保禁用列表存在
    if "disabledMcpjsonServers" not in project_config:
        project_config["disabledMcpjsonServers"] = []
    
    # 从禁用列表中移除（如果存在）
    if "claude-memory-mcp" in project_config["disabledMcpjsonServers"]:
        project_config["disabledMcpjsonServers"].remove("claude-memory-mcp")
    
    # 保存配置
    with open(claude_config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ 项目级MCP配置已修复")
    
    # 验证配置
    print("\n🔍 验证配置:")
    print(f"项目mcpServers: {list(project_config['mcpServers'].keys())}")
    print(f"启用的服务: {project_config['enabledMcpjsonServers']}")
    print(f"禁用的服务: {project_config['disabledMcpjsonServers']}")
    
    return True

if __name__ == "__main__":
    print("🚀 修复项目级MCP配置")
    print("=" * 40)
    
    if fix_project_mcp_config():
        print("\n🎉 修复完成！请重启Claude CLI测试。")
    else:
        print("\n❌ 修复失败。")