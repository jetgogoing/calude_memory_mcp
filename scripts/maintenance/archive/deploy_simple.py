#!/usr/bin/env python3
"""
简单部署脚本 - 一键配置Claude Memory MCP服务
"""

import json
import os
from pathlib import Path

def deploy():
    """部署Claude Memory MCP服务"""
    
    print("🚀 开始部署Claude Memory MCP服务...")
    
    # 1. 检查Claude配置文件
    claude_config = Path.home() / ".claude.json"
    
    if not claude_config.exists():
        print("❌ 未找到Claude配置文件 ~/.claude.json")
        print("请先启动Claude CLI一次以生成配置文件")
        return False
    
    # 2. 读取配置
    with open(claude_config, 'r') as f:
        config = json.load(f)
    
    # 3. 准备MCP服务器配置
    project_path = Path(__file__).parent
    venv_python = project_path / "venv-claude-memory" / "bin" / "python"
    simple_server = project_path / "simple_mcp_server.py"
    
    # 检查文件是否存在
    if not venv_python.exists():
        print(f"❌ 未找到Python虚拟环境: {venv_python}")
        return False
    
    if not simple_server.exists():
        print(f"❌ 未找到服务器文件: {simple_server}")
        return False
    
    # 4. 配置MCP服务器
    mcp_config = {
        "claude-memory": {
            "type": "stdio",
            "command": str(venv_python),
            "args": [str(simple_server)],
            "env": {
                "PYTHONPATH": str(project_path / "src"),
                "QDRANT_URL": "http://localhost:6333"
            }
        }
    }
    
    # 5. 更新配置
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    config["mcpServers"].update(mcp_config)
    
    # 6. 保存配置
    with open(claude_config, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Claude配置已更新")
    print(f"📁 项目路径: {project_path}")
    print(f"🐍 Python路径: {venv_python}")
    print(f"📄 服务器文件: {simple_server}")
    
    print("\n✨ 部署完成！")
    print("\n📋 使用说明:")
    print("1. 重启Claude CLI")
    print("2. 在Claude中输入 /mcp 查看服务状态")
    print("3. 使用工具: /mcp claude-memory memory_status")
    
    return True

if __name__ == "__main__":
    deploy()