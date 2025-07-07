#!/usr/bin/env python3
"""
更新Claude CLI配置为监控版MCP服务器
"""

import json
import os
import shutil
from pathlib import Path

def update_claude_cli_config():
    """更新Claude CLI配置"""
    
    # Claude CLI配置文件路径
    config_file = Path.home() / ".claude.json"
    backup_file = Path.home() / ".claude.json.backup"
    
    print("🔄 更新Claude CLI配置为监控版MCP服务器...")
    
    # 创建备份
    if config_file.exists():
        shutil.copy2(config_file, backup_file)
        print(f"✅ 配置备份已创建: {backup_file}")
    
    # 新的MCP配置
    mcp_config = {
        "mcpServers": {
            "claude-memory": {
                "command": "python",
                "args": ["/home/jetgogoing/claude_memory/monitoring_mcp_server.py"],
                "cwd": "/home/jetgogoing/claude_memory",
                "env": {
                    "PYTHONPATH": "/home/jetgogoing/claude_memory/src",
                    "PYTHONUNBUFFERED": "1"
                }
            }
        }
    }
    
    # 读取现有配置 (如果存在)
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                existing_config = json.load(f)
        except json.JSONDecodeError:
            existing_config = {}
    else:
        existing_config = {}
    
    # 合并配置
    existing_config.update(mcp_config)
    
    # 写入新配置
    with open(config_file, 'w') as f:
        json.dump(existing_config, f, indent=2)
    
    print(f"✅ Claude CLI配置已更新: {config_file}")
    print("📊 现在使用监控增强版MCP服务器")
    
    # 显示配置内容
    print("\n📋 更新后的MCP配置:")
    print(json.dumps(mcp_config, indent=2))

def update_systemd_service():
    """更新systemd服务配置"""
    
    print("\n🔄 更新systemd服务配置...")
    
    service_content = """[Unit]
Description=Claude Memory MCP Service with Monitoring
After=network.target postgresql.service

[Service]
Type=simple
User=jetgogoing
Group=jetgogoing
WorkingDirectory=/home/jetgogoing/claude_memory
Environment=PYTHONPATH=/home/jetgogoing/claude_memory/src
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/jetgogoing/claude_memory/venv-claude-memory/bin/python /home/jetgogoing/claude_memory/monitoring_mcp_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # 写入服务文件
    service_file = "/home/jetgogoing/claude_memory/claude-memory-mcp-monitoring.service"
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"✅ 监控版systemd服务配置已创建: {service_file}")
    
    # 提示安装命令
    print("\n📝 要安装服务，请运行:")
    print(f"sudo cp {service_file} /etc/systemd/system/")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable claude-memory-mcp-monitoring")
    print("sudo systemctl start claude-memory-mcp-monitoring")

def main():
    """主函数"""
    print("🚀 开始更新Claude Memory MCP配置为监控版...")
    
    # 更新Claude CLI配置
    update_claude_cli_config()
    
    # 更新systemd服务配置
    update_systemd_service()
    
    print("\n🎉 配置更新完成！")
    print("\n📊 监控功能:")
    print("• Prometheus指标: http://localhost:8080/metrics")
    print("• 健康检查API: http://localhost:8080/health") 
    print("• 增强版memory_health命令包含监控信息")
    
    print("\n🔄 下一步:")
    print("1. 重启Claude CLI进程以加载新配置")
    print("2. 运行 ./scripts/deploy_monitoring.sh 部署完整监控系统")
    print("3. 使用 /mcp claude-memory memory_health 测试监控功能")

if __name__ == "__main__":
    main()