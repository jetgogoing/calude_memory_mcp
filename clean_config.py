#!/usr/bin/env python3
"""
清理Claude配置中的重复MCP服务
"""

import json
from pathlib import Path

def clean_claude_config():
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    # 备份原配置
    backup_path = claude_config_path.with_suffix('.json.backup')
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    with open(backup_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✅ 已备份原配置到: {backup_path}")
    
    # 清理MCP配置
    if "mcpServers" in config:
        print("🔍 发现现有MCP配置:")
        for name, conf in config["mcpServers"].items():
            print(f"  - {name}: {conf.get('command', 'N/A')}")
        
        # 移除所有claude-memory相关配置
        config["mcpServers"].pop("claude-memory", None)
        config["mcpServers"].pop("claude-memory-mcp", None)
        print("🧹 已清理claude-memory相关配置")
    else:
        config["mcpServers"] = {}
    
    # 添加单一的clean配置
    config["mcpServers"]["claude-memory"] = {
        "type": "stdio",
        "command": "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
        "args": ["/home/jetgogoing/claude_memory/minimal_mcp_server.py"],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": "/home/jetgogoing/claude_memory/src"
        }
    }
    
    # 保存清理后的配置
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ 配置已清理并更新")
    print("📋 当前MCP配置:")
    print(f"  - claude-memory: minimal_mcp_server.py")
    
    return True

if __name__ == "__main__":
    clean_claude_config()