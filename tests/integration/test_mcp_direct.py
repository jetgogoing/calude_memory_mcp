#!/usr/bin/env python3
"""
直接测试MCP服务器响应
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

async def test_mcp_communication():
    """测试MCP通信"""
    project_root = Path(__file__).parent.parent.parent  # 回到项目根目录
    venv_python = project_root / "venv-claude-memory" / "bin" / "python"
    script_path = project_root / "fixed_production_mcp.py"
    
    # 启动MCP服务器进程
    proc = subprocess.Popen(
        [venv_python, script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # 发送初始化请求
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        # 发送请求
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        
        # 等待响应
        await asyncio.sleep(1)
        
        # 读取响应
        if proc.poll() is None:  # 进程还在运行
            print("✅ MCP服务器启动成功，等待响应中...")
            
            # 发送tools列表请求
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            proc.stdin.write(json.dumps(tools_request) + "\n")
            proc.stdin.flush()
            
            await asyncio.sleep(1)
            print("✅ 工具列表请求已发送")
            
        else:
            print("❌ MCP服务器进程已退出")
            stderr_output = proc.stderr.read()
            if stderr_output:
                print(f"错误输出: {stderr_output}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

def main():
    print("🧪 直接测试MCP服务器通信")
    print("=" * 40)
    
    asyncio.run(test_mcp_communication())
    
    print("\n💡 如果服务器启动成功但Claude CLI显示failed，")
    print("   可能是Claude CLI的MCP集成配置问题。")

if __name__ == "__main__":
    main()