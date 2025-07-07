#!/usr/bin/env python3
"""
强制MCP测试 - 直接调用MCP服务器验证功能
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加src到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

async def test_mcp_direct():
    """直接测试MCP服务器"""
    try:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import stdio_client
        import subprocess
        
        print("🚀 启动MCP服务器进程...")
        
        # 启动MCP服务器进程
        server_path = project_root / "simple_mcp_server.py"
        python_path = project_root / "venv-claude-memory" / "bin" / "python"
        
        process = await asyncio.create_subprocess_exec(
            str(python_path), str(server_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print("✅ MCP服务器进程已启动")
        
        # 创建MCP客户端
        async with stdio_client(process.stdin, process.stdout) as (read, write):
            async with ClientSession(read, write) as session:
                print("🔗 已连接到MCP服务器")
                
                # 初始化
                await session.initialize()
                print("✅ MCP会话初始化完成")
                
                # 列出工具
                tools_result = await session.list_tools()
                print(f"🛠️ 可用工具数量: {len(tools_result.tools)}")
                for tool in tools_result.tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # 测试工具调用
                print("\n🧪 测试工具调用...")
                status_result = await session.call_tool("get_service_status", {})
                print("✅ get_service_status 调用成功:")
                for content in status_result.content:
                    if hasattr(content, 'text'):
                        print(f"   {content.text}")
                
                print("\n🔍 测试记忆搜索...")
                search_result = await session.call_tool("search_memories", {
                    "query": "测试搜索",
                    "limit": 3
                })
                print("✅ search_memories 调用成功:")
                for content in search_result.content:
                    if hasattr(content, 'text'):
                        print(f"   {content.text}")
        
        # 终止进程
        process.terminate()
        await process.wait()
        print("\n🎉 所有MCP功能测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ MCP测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_format():
    """测试配置文件格式"""
    print("\n📄 验证MCP配置文件格式...")
    
    config_path = Path.home() / ".claude" / "mcp_servers.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # 检查必要字段
        if "claude-memory-mcp" not in config:
            print("❌ 配置中缺少 'claude-memory-mcp' 条目")
            return False
        
        mcp_config = config["claude-memory-mcp"]
        required_fields = ["command", "args"]
        
        for field in required_fields:
            if field not in mcp_config:
                print(f"❌ 配置中缺少必需字段: {field}")
                return False
        
        print("✅ MCP配置文件格式正确")
        
        # 验证路径
        python_path = Path(mcp_config["command"])
        server_path = Path(mcp_config["args"][0])
        
        if not python_path.exists():
            print(f"❌ Python路径不存在: {python_path}")
            return False
        
        if not server_path.exists():
            print(f"❌ 服务器脚本不存在: {server_path}")
            return False
        
        print("✅ 配置路径验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置文件验证失败: {e}")
        return False

async def main():
    print("🔬 Claude Memory MCP强制测试")
    print("=" * 50)
    
    # 测试配置
    config_ok = test_config_format()
    
    if config_ok:
        # 直接测试MCP功能
        mcp_ok = await test_mcp_direct()
        
        if mcp_ok:
            print("\n🎊 结论: MCP服务器功能完全正常!")
            print("💡 如果Claude CLI仍然看不到MCP服务，可能是:")
            print("   1. Claude CLI版本不支持MCP功能")
            print("   2. Claude CLI未正确读取配置文件")
            print("   3. 需要特殊的Claude CLI启动参数")
            print("\n🔧 建议尝试:")
            print("   - 重新安装Claude CLI")
            print("   - 查看Claude CLI文档中的MCP配置说明")
            print("   - 联系Claude CLI支持")
        else:
            print("\n❌ MCP服务器存在问题")
    else:
        print("\n❌ 配置文件存在问题")

if __name__ == "__main__":
    asyncio.run(main())