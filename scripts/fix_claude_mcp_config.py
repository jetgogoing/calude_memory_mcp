#!/usr/bin/env python3
"""
修复Claude CLI MCP配置
更新.claude.json中的MCP服务器配置
"""

import json
import os
from pathlib import Path

def fix_claude_config():
    """修复Claude CLI配置"""
    
    # 配置文件路径
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    # 读取当前配置
    try:
        with open(claude_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ 成功读取Claude配置文件")
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False
    
    # 正确的MCP配置
    project_path = "/home/jetgogoing/claude_memory"
    correct_mcp_config = {
        "claude-memory-mcp": {
            "type": "stdio",
            "command": f"{project_path}/venv-claude-memory/bin/python",
            "args": [f"{project_path}/simple_mcp_server.py"],
            "env": {
                "QDRANT_URL": "http://localhost:6333",
                "QDRANT_API_KEY": "",
                "SILICONFLOW_API_KEY": "sk-tjjznxtevmlynypmydlhqepnatclvlrimsygimtyafdoxklw",
                "GEMINI_API_KEY": "AIzaSyDTBboAMDzVY7UMKK5gbNhwKufNTSDY0sw",
                "OPENROUTER_API_KEY": "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"
            }
        }
    }
    
    print("\n🔧 修复配置...")
    
    # 1. 更新全局MCP配置
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # 移除旧的claude-memory配置
    if "claude-memory" in config["mcpServers"]:
        del config["mcpServers"]["claude-memory"]
        print("✅ 移除旧的claude-memory配置")
    
    # 添加新的配置
    config["mcpServers"].update(correct_mcp_config)
    print("✅ 更新全局MCP配置")
    
    # 2. 更新项目级配置
    if project_path not in config.get("projects", {}):
        if "projects" not in config:
            config["projects"] = {}
        config["projects"][project_path] = {
            "allowedTools": [],
            "history": [],
            "mcpContextUris": [],
            "mcpServers": {},
            "enabledMcpjsonServers": [],
            "disabledMcpjsonServers": [],
            "hasTrustDialogAccepted": False,
            "projectOnboardingSeenCount": 0,
            "hasClaudeMdExternalIncludesApproved": False,
            "hasClaudeMdExternalIncludesWarningShown": False
        }
    
    # 更新项目的MCP配置
    project_config = config["projects"][project_path]
    
    # 确保必要字段存在
    for field in ["mcpServers", "enabledMcpjsonServers", "disabledMcpjsonServers"]:
        if field not in project_config:
            project_config[field] = [] if field.endswith("Servers") else {}
    
    # 添加MCP服务到项目配置
    project_config["mcpServers"].update(correct_mcp_config)
    
    # 启用MCP服务
    if "claude-memory-mcp" not in project_config["enabledMcpjsonServers"]:
        project_config["enabledMcpjsonServers"].append("claude-memory-mcp")
    
    print("✅ 更新项目级MCP配置")
    
    # 3. 保存配置
    try:
        # 备份原配置
        backup_path = claude_config_path.with_suffix('.json.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ 配置已备份到: {backup_path}")
        
        # 保存新配置
        with open(claude_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ 配置已更新")
        
    except Exception as e:
        print(f"❌ 保存配置失败: {e}")
        return False
    
    print("\n🎉 MCP配置修复完成！")
    print("\n📋 下一步操作:")
    print("1. 重启Claude CLI")
    print("2. 在Claude CLI中输入: /mcp")
    print("3. 应该能看到 'claude-memory-mcp' 服务")
    
    return True

def verify_files():
    """验证必要文件是否存在"""
    print("🔍 验证文件...")
    
    files_to_check = [
        "/home/jetgogoing/claude_memory/venv-claude-memory/bin/python",
        "/home/jetgogoing/claude_memory/simple_mcp_server.py"
    ]
    
    all_exist = True
    for file_path in files_to_check:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - 文件不存在")
            all_exist = False
    
    return all_exist

if __name__ == "__main__":
    print("🚀 Claude CLI MCP配置修复工具")
    print("=" * 50)
    
    # 验证文件
    if not verify_files():
        print("\n❌ 必要文件缺失，请先确保所有文件存在")
        exit(1)
    
    # 修复配置
    if fix_claude_config():
        print("\n🎊 修复成功！请重启Claude CLI测试。")
    else:
        print("\n❌ 修复失败，请检查错误信息。")