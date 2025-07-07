#!/usr/bin/env python3
"""
更新配置使用Echo服务器进行测试
"""

import json
from pathlib import Path

def update_to_echo():
    claude_config_path = Path.home() / ".claude.json"
    
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    # 更新为echo服务器
    config["mcpServers"]["claude-memory"] = {
        "type": "stdio",
        "command": "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
        "args": ["/home/jetgogoing/claude_memory/echo_mcp_server.py"],
        "env": {
            "PYTHONUNBUFFERED": "1"
        }
    }
    
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ 已更新配置使用Echo MCP服务器")
    print("🔄 请重启Claude CLI后测试")

if __name__ == "__main__":
    update_to_echo()