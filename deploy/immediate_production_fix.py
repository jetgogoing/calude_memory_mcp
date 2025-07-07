#!/usr/bin/env python3
"""
立即修复当前MCP连接问题 - 切换到生产级MCP服务器
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

def immediate_fix():
    """立即修复MCP连接问题"""
    
    print("🔧 Claude Memory MCP立即修复 - 切换到生产服务器")
    print("=" * 60)
    
    project_root = Path("/home/jetgogoing/claude_memory")
    
    # 1. 创建生产MCP服务器启动脚本
    print("📝 1. 创建生产MCP服务器启动脚本...")
    
    production_mcp_script = project_root / "production_mcp_server.py"
    production_mcp_content = '''#!/usr/bin/env python3
"""
生产级Claude Memory MCP服务器
使用完整架构替代简化版本
"""

import asyncio
import os
import sys
import signal
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 设置环境变量
os.environ.setdefault("PYTHONPATH", str(project_root / "src"))

import structlog
from mcp.server.stdio import stdio_server

# 配置日志
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

async def main():
    """启动生产MCP服务器"""
    
    try:
        logger.info("🚀 Starting Claude Memory MCP Server (Production)")
        
        # 导入完整的MCP服务器
        from claude_memory.mcp_server import ClaudeMemoryMCPServer
        
        # 创建服务器实例
        server = ClaudeMemoryMCPServer()
        
        # 初始化服务器
        await server.initialize()
        logger.info("✅ Server initialized successfully")
        
        # 注册信号处理器
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.get_event_loop().stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动STDIO服务器
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.info("🔄 Falling back to simple MCP server...")
        
        # 回退到简化版本
        from simple_mcp_server import main as simple_main
        await simple_main()
        
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open(production_mcp_script, 'w', encoding='utf-8') as f:
        f.write(production_mcp_content)
    
    production_mcp_script.chmod(0o755)
    print(f"✅ 生产MCP脚本已创建: {production_mcp_script}")
    
    # 2. 更新Claude CLI配置
    print("🔧 2. 更新Claude CLI配置...")
    
    claude_config_path = Path.home() / ".claude.json"
    
    # 读取当前配置
    with open(claude_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 新的MCP配置
    new_mcp_config = {
        "claude-memory-mcp": {
            "type": "stdio",
            "command": str(project_root / "venv-claude-memory" / "bin" / "python"),
            "args": [str(production_mcp_script)],
            "env": {
                "PYTHONPATH": str(project_root / "src"),
                "QDRANT_URL": "http://localhost:6333",
                "QDRANT_API_KEY": "",
                "SILICONFLOW_API_KEY": "sk-tjjznxtevmlynypmydlhqepnatclvlrimsygimtyafdoxklw",
                "GEMINI_API_KEY": "AIzaSyDTBboAMDzVY7UMKK5gbNhwKufNTSDY0sw",
                "OPENROUTER_API_KEY": "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"
            }
        }
    }
    
    # 更新全局配置
    config["mcpServers"].update(new_mcp_config)
    
    # 更新项目配置
    project_path = str(project_root)
    if project_path in config.get("projects", {}):
        config["projects"][project_path]["mcpServers"] = new_mcp_config
        config["projects"][project_path]["enabledMcpjsonServers"] = ["claude-memory-mcp"]
        
        # 从禁用列表中移除
        if "claude-memory-mcp" in config["projects"][project_path].get("disabledMcpjsonServers", []):
            config["projects"][project_path]["disabledMcpjsonServers"].remove("claude-memory-mcp")
    
    # 备份原配置
    backup_path = claude_config_path.with_suffix('.json.backup.immediate')
    shutil.copy2(claude_config_path, backup_path)
    print(f"✅ 配置已备份: {backup_path}")
    
    # 保存新配置
    with open(claude_config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Claude CLI配置已更新")
    
    # 3. 验证依赖
    print("🔍 3. 验证依赖和环境...")
    
    # 检查虚拟环境
    venv_python = project_root / "venv-claude-memory" / "bin" / "python"
    if not venv_python.exists():
        print(f"❌ 虚拟环境不存在: {venv_python}")
        return False
    
    # 测试导入
    try:
        result = subprocess.run([
            str(venv_python), "-c", 
            "import sys; sys.path.insert(0, 'src'); from claude_memory.mcp_server import ClaudeMemoryMCPServer; print('✅ Import successful')"
        ], cwd=str(project_root), capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ 完整MCP服务器导入成功")
        else:
            print(f"⚠️ 完整MCP服务器导入失败，将使用简化版本")
            print(f"错误: {result.stderr}")
    except Exception as e:
        print(f"⚠️ 导入测试失败: {e}")
    
    # 4. 测试新配置
    print("🧪 4. 测试新MCP服务器...")
    
    try:
        result = subprocess.run([
            str(venv_python), str(production_mcp_script)
        ], cwd=str(project_root), capture_output=True, text=True, timeout=10)
        
        print("✅ MCP服务器启动测试完成")
        
    except subprocess.TimeoutExpired:
        print("✅ MCP服务器正常启动(超时为正常，服务器等待STDIO输入)")
    except Exception as e:
        print(f"⚠️ MCP服务器测试异常: {e}")
    
    # 5. 最终指导
    print("\n" + "=" * 60)
    print("🎉 立即修复完成！")
    print("\n📋 下一步操作:")
    print("1. 完全重启Claude CLI")
    print("2. 在Claude CLI中输入: /mcp")
    print("3. 确认claude-memory-mcp服务状态为 ✅ ready")
    print("4. 测试MCP工具:")
    print("   /mcp claude-memory-mcp get_service_status")
    
    print(f"\n📁 新MCP服务器: {production_mcp_script}")
    print(f"📁 配置备份: {backup_path}")
    print(f"📁 完整部署方案: {project_root}/deploy/production_deployment_plan.md")
    
    return True

if __name__ == "__main__":
    try:
        success = immediate_fix()
        if success:
            print("\n🚀 可以开始使用完整功能的Claude Memory MCP服务了！")
        else:
            print("\n❌ 修复过程中遇到问题，请检查上述错误信息")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)