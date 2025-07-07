#!/usr/bin/env python3
"""
更新Claude配置使用最小化MCP服务器
"""

import json
from pathlib import Path

def update_claude_config():
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    # 读取配置
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    # 清理旧的配置
    if "mcpServers" in config:
        config["mcpServers"].pop("claude-memory-mcp", None)
        config["mcpServers"].pop("claude-memory", None)
    else:
        config["mcpServers"] = {}
    
    # 添加新的最小化配置
    config["mcpServers"]["claude-memory"] = {
        "type": "stdio",
        "command": "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
        "args": ["/home/jetgogoing/claude_memory/minimal_mcp_server.py"],
        "env": {}
    }
    
    # 保存配置
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Claude配置已更新为最小化MCP服务器")
    print("🔄 请重启Claude CLI后测试")
    return True

if __name__ == "__main__":
    update_claude_config()