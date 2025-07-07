#!/usr/bin/env python3
"""
彻底删除失败的claude-memory-mcp配置
"""

import json
from pathlib import Path

def remove_failed_config():
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    print("🔍 当前MCP配置:")
    mcp_servers = config.get("mcpServers", {})
    for name, conf in mcp_servers.items():
        status = "✅" if "working" in conf.get("args", [""])[0] else "❌"
        print(f"  {status} {name}: {conf.get('args', ['N/A'])[0]}")
    
    # 删除失败的claude-memory-mcp配置
    removed = config["mcpServers"].pop("claude-memory-mcp", None)
    
    if removed:
        print(f"\n🗑️  已删除失败的配置: claude-memory-mcp")
        print(f"   文件: {removed.get('args', ['N/A'])[0]}")
    else:
        print("\nℹ️  未找到claude-memory-mcp配置")
    
    # 保存清理后的配置
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n✅ 配置已清理")
    print("📋 剩余MCP服务:")
    for name in config["mcpServers"].keys():
        print(f"  - {name}")
    
    return True

if __name__ == "__main__":
    remove_failed_config()