#!/usr/bin/env python3
"""
部署正常工作的MCP服务器
"""

import json
from pathlib import Path

def deploy_working_server():
    claude_config_path = Path.home() / ".claude.json"
    
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    # 清理并更新配置
    config["mcpServers"].pop("claude-memory-mcp", None)
    
    # 使用工作版本
    config["mcpServers"]["claude-memory"] = {
        "type": "stdio",
        "command": "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
        "args": ["/home/jetgogoing/claude_memory/working_mcp_server.py"],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": "/home/jetgogoing/claude_memory/src"
        }
    }
    
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ 已部署正常工作的MCP服务器")
    print("🔄 请重启Claude CLI后测试完整功能")
    print("\n🧪 测试命令:")
    print("- /mcp claude-memory memory_status")
    print("- /mcp claude-memory memory_health") 
    print("- /mcp claude-memory memory_search query='Python编程'")

if __name__ == "__main__":
    deploy_working_server()