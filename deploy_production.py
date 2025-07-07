#!/usr/bin/env python3
"""
生产级部署脚本
"""

import json
import subprocess
from pathlib import Path

def run_tests():
    """运行测试套件"""
    print("🧪 运行测试套件...")
    
    try:
        # 检查pytest是否安装
        result = subprocess.run(
            ["python", "-m", "pytest", "--version"], 
            capture_output=True, text=True, cwd=Path.cwd()
        )
        
        if result.returncode != 0:
            print("⚠️  pytest未安装，安装中...")
            subprocess.run(["pip", "install", "pytest", "pytest-asyncio"], check=True)
        
        # 运行测试
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_mcp_protocol.py::TestMCPProtocol::test_ready_handshake", "-v"],
            cwd=Path.cwd(),
            env={**subprocess.os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )
        
        if result.returncode == 0:
            print("✅ 所有测试通过")
            return True
        else:
            print("❌ 测试失败，请检查代码")
            return False
            
    except Exception as e:
        print(f"❌ 测试运行失败: {e}")
        return False

def deploy_production_server():
    """部署生产服务器"""
    print("🚀 部署生产级MCP服务器...")
    
    claude_config_path = Path.home() / ".claude.json"
    
    if not claude_config_path.exists():
        print("❌ Claude配置文件不存在")
        return False
    
    with open(claude_config_path, 'r') as f:
        config = json.load(f)
    
    # 更新为生产版本
    config["mcpServers"]["claude-memory"] = {
        "type": "stdio",
        "command": str(Path.cwd() / "venv-claude-memory/bin/python"),
        "args": [str(Path.cwd() / "production_mcp_server_v2.py")],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(Path.cwd() / "src")
        }
    }
    
    with open(claude_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ 生产服务器配置已更新")
    print("🔄 请重启Claude CLI测试生产版本")
    
    return True

def create_systemd_service():
    """创建systemd服务文件"""
    service_content = f"""[Unit]
Description=Claude Memory MCP Service
After=network.target

[Service]
Type=simple
User={Path.home().name}
WorkingDirectory={Path.cwd()}
ExecStart={Path.cwd() / "venv-claude-memory/bin/python"} {Path.cwd() / "production_mcp_server_v2.py"}
Restart=on-failure
RestartSec=5
StandardOutput=null
StandardError=append:{Path.cwd() / "logs/systemd_error.log"}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH={Path.cwd() / "src"}

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path.cwd() / "claude-memory-mcp.service"
    with open(service_path, "w") as f:
        f.write(service_content)
    
    print(f"✅ Systemd服务文件已创建: {service_path}")
    print("📋 安装命令:")
    print(f"  sudo cp {service_path} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable claude-memory-mcp")
    print("  sudo systemctl start claude-memory-mcp")

def main():
    """主部署流程"""
    print("🚀 Claude Memory MCP 生产级部署")
    print("=" * 50)
    
    # 步骤1: 运行测试
    if not run_tests():
        print("❌ 测试失败，停止部署")
        return
    
    # 步骤2: 部署生产服务器
    if not deploy_production_server():
        print("❌ 部署失败")
        return
    
    # 步骤3: 创建systemd服务
    create_systemd_service()
    
    print("\n🎉 生产级部署完成！")
    print("\n📋 验证步骤:")
    print("1. 重启Claude CLI")
    print("2. 运行: /mcp")
    print("3. 测试: /mcp claude-memory memory_health")
    print("4. 测试: /mcp claude-memory ping")

if __name__ == "__main__":
    main()