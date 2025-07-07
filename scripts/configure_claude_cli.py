#!/usr/bin/env python3
"""
Claude CLI MCP集成配置脚本
自动配置Claude CLI使用Claude Memory MCP服务
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

def main():
    """主配置流程"""
    print("🔧 Claude Memory MCP服务 - Claude CLI集成配置")
    print("=" * 60)
    
    # 检测Claude CLI配置目录
    claude_config_dirs = [
        Path.home() / ".claude",
        Path.home() / ".config" / "claude",
        Path("/etc/claude")
    ]
    
    claude_config_dir = None
    for config_dir in claude_config_dirs:
        if config_dir.exists():
            claude_config_dir = config_dir
            break
    
    if not claude_config_dir:
        print("❌ 未找到Claude CLI配置目录")
        print("请先安装和配置Claude CLI")
        print("参考: https://docs.anthropic.com/claude/docs/claude-cli")
        sys.exit(1)
    
    print(f"📁 Claude CLI配置目录: {claude_config_dir}")
    
    # MCP服务器配置文件路径
    mcp_config_file = claude_config_dir / "mcp_servers.json"
    
    # 当前项目路径
    project_root = Path(__file__).parent.parent
    
    # Claude Memory MCP服务配置
    claude_memory_config = {
        "claude-memory-mcp": {
            "command": "python",
            "args": [
                "-m", "claude_memory.mcp_server"
            ],
            "env": {
                "PYTHONPATH": str(project_root / "src")
            },
            "cwd": str(project_root)
        }
    }
    
    # 读取现有配置
    existing_config = {}
    if mcp_config_file.exists():
        try:
            with open(mcp_config_file, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
            print(f"📋 读取现有MCP配置: {len(existing_config)}个服务")
        except json.JSONDecodeError as e:
            print(f"⚠️  现有MCP配置文件格式错误: {e}")
            response = input("是否备份现有文件并创建新配置? (y/N): ").strip().lower()
            if response != 'y':
                print("🚫 配置已取消")
                sys.exit(0)
            
            # 备份现有文件
            backup_file = mcp_config_file.with_suffix('.json.backup')
            mcp_config_file.rename(backup_file)
            print(f"💾 已备份现有配置到: {backup_file}")
            existing_config = {}
    
    # 检查是否已配置Claude Memory MCP
    if "claude-memory-mcp" in existing_config:
        print("🔍 检测到现有Claude Memory MCP配置")
        print(f"   现有配置: {json.dumps(existing_config['claude-memory-mcp'], indent=2)}")
        
        response = input("是否更新现有配置? (y/N): ").strip().lower()
        if response != 'y':
            print("✅ 保持现有配置不变")
            sys.exit(0)
    
    # 合并配置
    updated_config = existing_config.copy()
    updated_config.update(claude_memory_config)
    
    # 写入配置文件
    try:
        # 确保配置目录存在
        mcp_config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(mcp_config_file, 'w', encoding='utf-8') as f:
            json.dump(updated_config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ MCP配置已更新: {mcp_config_file}")
        
        # 显示配置摘要
        print(f"\n📋 配置摘要:")
        print(f"   📁 配置文件: {mcp_config_file}")
        print(f"   🔧 MCP服务数量: {len(updated_config)}")
        print(f"   📦 Claude Memory MCP: ✅ 已配置")
        print(f"   🗂️  项目路径: {project_root}")
        print(f"   🐍 Python路径: {project_root / 'src'}")
        
        # 验证配置
        print(f"\n🔍 验证配置...")
        
        # 检查Python模块是否可访问
        mcp_module = project_root / "src" / "claude_memory" / "mcp_server.py"
        if mcp_module.exists():
            print(f"   ✅ MCP服务器模块存在")
        else:
            print(f"   ❌ MCP服务器模块不存在: {mcp_module}")
        
        # 检查环境配置
        env_file = project_root / "config" / ".env"
        if env_file.exists():
            print(f"   ✅ 环境配置文件存在")
        else:
            print(f"   ⚠️  环境配置文件不存在: {env_file}")
            print(f"       请运行: python scripts/setup_api_keys.py")
        
        print(f"\n🚀 下一步:")
        print(f"   1. 确保所有API密钥已配置")
        print(f"   2. 启动Qdrant服务: bash scripts/start_qdrant.sh")
        print(f"   3. 测试MCP服务: python scripts/test_mcp_integration.py")
        print(f"   4. 重启Claude CLI以加载新配置")
        
    except Exception as e:
        print(f"❌ 配置文件写入失败: {e}")
        sys.exit(1)

def create_claude_cli_config():
    """创建完整的Claude CLI配置示例"""
    claude_config_dir = Path.home() / ".claude"
    claude_config_dir.mkdir(exist_ok=True)
    
    # 创建完整配置示例
    full_config = {
        "api_key": "your_anthropic_api_key_here",
        "default_model": "claude-3-5-sonnet-20241022",
        "mcp_servers": {
            "claude-memory-mcp": {
                "command": "python",
                "args": ["-m", "claude_memory.mcp_server"],
                "env": {
                    "PYTHONPATH": str(Path.cwd() / "src")
                },
                "cwd": str(Path.cwd())
            }
        },
        "settings": {
            "max_tokens": 4096,
            "temperature": 0.7,
            "enable_mcp": True
        }
    }
    
    config_file = claude_config_dir / "config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(full_config, f, indent=2, ensure_ascii=False)
    
    print(f"📝 创建Claude CLI配置示例: {config_file}")
    print("⚠️  请编辑此文件并添加实际的API密钥")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n🚫 配置已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 配置过程出错: {e}")
        sys.exit(1)