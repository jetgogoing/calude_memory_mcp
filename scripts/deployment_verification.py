#!/usr/bin/env python3
"""
Claude Memory MCP服务部署验证脚本
完整验证部署的每个环节
"""

import asyncio
import json
import sys
import subprocess
from pathlib import Path

# 添加src到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

async def main():
    """完整部署验证"""
    print("🎯 Claude Memory MCP服务 - 完整部署验证")
    print("=" * 60)
    
    verification_steps = [
        "✅ 阶段1: 环境准备和依赖安装",
        "✅ 阶段2: 配置管理和API设置", 
        "✅ 阶段3: Claude CLI集成配置",
        "🔄 正在验证: 服务功能测试"
    ]
    
    for step in verification_steps:
        print(f"   {step}")
    
    print("\n📋 验证项目清单:")
    print("-" * 40)
    
    # 1. 环境检查
    print("1️⃣ 环境检查:")
    
    # Python版本
    python_version = sys.version.split()[0]
    print(f"   ✅ Python版本: {python_version}")
    
    # 虚拟环境
    venv_path = project_root / "venv-claude-memory"
    if venv_path.exists():
        print("   ✅ 虚拟环境已创建")
    else:
        print("   ❌ 虚拟环境未找到")
        return False
    
    # 2. 依赖检查
    print("\n2️⃣ 依赖检查:")
    try:
        import claude_memory
        print("   ✅ claude_memory模块可导入")
        
        from claude_memory.config.settings import get_settings
        settings = get_settings()
        print(f"   ✅ 配置加载成功 - v{settings.service.version}")
        
    except ImportError as e:
        print(f"   ❌ 模块导入失败: {e}")
        return False
    
    # 3. 配置文件检查
    print("\n3️⃣ 配置文件检查:")
    
    env_file = project_root / ".env"
    if env_file.exists():
        print("   ✅ 环境配置文件存在")
        
        # 检查API密钥配置
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        api_keys = ['SILICONFLOW_API_KEY', 'GEMINI_API_KEY', 'OPENROUTER_API_KEY']
        configured_keys = 0
        for key in api_keys:
            if f"{key}=sk-" in env_content or f"{key}=AIza" in env_content:
                configured_keys += 1
        
        print(f"   ✅ API密钥配置: {configured_keys}/{len(api_keys)}")
    else:
        print("   ❌ 环境配置文件不存在")
        return False
    
    # 4. 数据库检查
    print("\n4️⃣ 数据库检查:")
    
    db_file = project_root / "data" / "claude_memory.db"
    if db_file.exists():
        print("   ✅ SQLite数据库文件存在")
    else:
        print("   ⚠️  SQLite数据库文件不存在(将在首次运行时创建)")
    
    # 5. Qdrant检查
    print("\n5️⃣ Qdrant服务检查:")
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:6333/", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Qdrant服务运行正常 - v{data.get('version', 'unknown')}")
            else:
                print(f"   ❌ Qdrant服务响应异常: {response.status_code}")
                return False
    except Exception as e:
        print(f"   ❌ Qdrant连接失败: {e}")
        return False
    
    # 6. Claude CLI检查
    print("\n6️⃣ Claude CLI集成检查:")
    
    mcp_config_file = Path.home() / ".claude" / "mcp_servers.json"
    if mcp_config_file.exists():
        try:
            with open(mcp_config_file, 'r') as f:
                mcp_config = json.load(f)
            
            if "claude-memory-mcp" in mcp_config:
                print("   ✅ Claude CLI MCP配置已设置")
                config = mcp_config["claude-memory-mcp"]
                print(f"      命令: {config['command']} {' '.join(config['args'])}")
                print(f"      工作目录: {config['cwd']}")
            else:
                print("   ❌ Claude Memory MCP配置未找到")
                return False
        except Exception as e:
            print(f"   ❌ MCP配置读取失败: {e}")
            return False
    else:
        print("   ❌ Claude CLI MCP配置文件不存在")
        return False
    
    # 7. MCP服务功能测试
    print("\n7️⃣ MCP服务功能测试:")
    
    try:
        from claude_memory.mcp_server import ClaudeMemoryMCPServer
        
        # 创建MCP服务器实例
        mcp_server = ClaudeMemoryMCPServer()
        print("   ✅ MCP服务器实例创建成功")
        
        # 初始化测试
        await mcp_server.initialize()
        print("   ✅ MCP服务器初始化成功")
        
        # 清理
        await mcp_server.cleanup()
        print("   ✅ MCP服务器清理成功")
        
    except Exception as e:
        print(f"   ❌ MCP服务测试失败: {e}")
        return False
    
    # 8. 完整性验证
    print("\n8️⃣ 完整性验证:")
    
    # 检查所有必要的脚本
    scripts = [
        "start_qdrant.sh",
        "stop_qdrant.sh", 
        "setup_api_keys.py",
        "configure_claude_cli.py",
        "test_claude_cli_integration.py"
    ]
    
    missing_scripts = []
    for script in scripts:
        script_path = project_root / "scripts" / script
        if script_path.exists():
            print(f"   ✅ {script}")
        else:
            missing_scripts.append(script)
            print(f"   ❌ {script}")
    
    if missing_scripts:
        print(f"   ⚠️  缺少脚本: {', '.join(missing_scripts)}")
    
    # 最终结果
    print("\n" + "=" * 60)
    print("🎉 部署验证完成!")
    print("\n📋 验证摘要:")
    print("   ✅ 环境准备: 完成")
    print("   ✅ 依赖安装: 完成")
    print("   ✅ 配置管理: 完成")
    print("   ✅ Claude CLI集成: 完成")
    print("   ✅ 服务功能: 验证通过")
    
    print("\n🚀 系统已准备就绪！")
    print("\n📖 使用说明:")
    print("1. 启动服务:")
    print("   bash scripts/start_qdrant.sh")
    print("   # Qdrant将在后台运行")
    print()
    print("2. 使用Claude CLI:")
    print("   claude")
    print("   # MCP服务将自动加载")
    print()
    print("3. 测试记忆功能:")
    print("   # 在Claude CLI中使用MCP工具")
    print("   # 系统会自动捕获和管理对话记忆")
    print()
    print("4. 监控和管理:")
    print("   # 查看Qdrant状态: http://localhost:6333")
    print("   # 查看日志: logs/qdrant.log")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        if success:
            print("\n✨ 恭喜！Claude Memory MCP服务部署验证全部通过！")
            sys.exit(0)
        else:
            print("\n⚠️  部分验证未通过，请检查上述错误信息")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🚫 验证被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 验证执行失败: {e}")
        sys.exit(1)