#!/usr/bin/env python3
"""
最终清理 - 彻底删除所有claude-memory-mcp配置
"""

import json
from pathlib import Path

def final_cleanup():
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    # 创建备份
    backup_path = claude_config_path.with_suffix('.json.final_backup')
    
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    with open(backup_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✅ 已备份到: {backup_path}")
    
    # 清理所有claude-memory-mcp引用
    changes_made = 0
    
    # 清理全局mcpServers
    if "mcpServers" in config:
        if "claude-memory-mcp" in config["mcpServers"]:
            del config["mcpServers"]["claude-memory-mcp"]
            changes_made += 1
            print("🗑️  删除全局claude-memory-mcp配置")
    
    # 清理所有项目配置
    if "projects" in config:
        for project_path, project_config in config["projects"].items():
            if "mcpServers" in project_config:
                if "claude-memory-mcp" in project_config["mcpServers"]:
                    del project_config["mcpServers"]["claude-memory-mcp"]
                    changes_made += 1
                    print(f"🗑️  删除项目 {project_path} 中的claude-memory-mcp配置")
    
    # 保存配置
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ 清理完成，共删除 {changes_made} 个配置项")
    
    # 显示剩余的MCP配置
    print("\n📋 剩余MCP配置:")
    
    # 全局配置
    global_servers = config.get("mcpServers", {})
    if global_servers:
        print("  全局:")
        for name in global_servers.keys():
            print(f"    - {name}")
    
    # 项目配置
    if "projects" in config:
        for project_path, project_config in config["projects"].items():
            project_servers = project_config.get("mcpServers", {})
            if project_servers:
                print(f"  项目 {project_path}:")
                for name in project_servers.keys():
                    print(f"    - {name}")
    
    return True

if __name__ == "__main__":
    final_cleanup()