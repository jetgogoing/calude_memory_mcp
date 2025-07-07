#!/usr/bin/env python3
"""
MCP协议单元测试
测试服务器的核心协议功能
"""

import pytest
import json
import subprocess
import asyncio
import os
from pathlib import Path

class TestMCPProtocol:
    """MCP协议测试套件"""
    
    @pytest.fixture
    def server_path(self):
        """获取服务器脚本路径"""
        return Path(__file__).parent.parent / "working_mcp_server.py"
    
    @pytest.fixture
    def python_path(self):
        """获取Python解释器路径"""
        return Path(__file__).parent.parent / "venv-claude-memory/bin/python"
    
    async def _send_message(self, process, message):
        """发送消息到MCP服务器"""
        json_str = json.dumps(message) + "\n"
        process.stdin.write(json_str.encode())
        await process.stdin.drain()
    
    async def _read_response(self, process, timeout=5):
        """读取MCP服务器响应"""
        try:
            line = await asyncio.wait_for(
                process.stdout.readline(), 
                timeout=timeout
            )
            if line:
                return json.loads(line.decode().strip())
        except asyncio.TimeoutError:
            pytest.fail(f"服务器响应超时 (>{timeout}s)")
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON解析失败: {e}")
        return None
    
    @pytest.mark.asyncio
    async def test_ready_handshake(self, python_path, server_path):
        """测试1: Ready握手"""
        # 启动服务器进程
        process = await asyncio.create_subprocess_exec(
            str(python_path), str(server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        try:
            # 应该立即收到ready信号
            ready_msg = await self._read_response(process, timeout=3)
            
            assert ready_msg is not None, "未收到ready消息"
            assert ready_msg.get("jsonrpc") == "2.0", "协议版本错误"
            assert ready_msg.get("method") == "notifications/initialized", "Ready消息格式错误"
            
            print("✅ Ready握手测试通过")
            
        finally:
            process.terminate()
            await process.wait()
    
    @pytest.mark.asyncio
    async def test_initialize_exchange(self, python_path, server_path):
        """测试2: 初始化交换"""
        process = await asyncio.create_subprocess_exec(
            str(python_path), str(server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        try:
            # 跳过ready消息
            await self._read_response(process)
            
            # 发送初始化请求
            init_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }
            
            await self._send_message(process, init_msg)
            response = await self._read_response(process)
            
            assert response is not None, "未收到初始化响应"
            assert response.get("id") == 1, "响应ID不匹配"
            assert "result" in response, "响应缺少result字段"
            assert response["result"].get("protocolVersion") == "2024-11-05"
            assert "serverInfo" in response["result"]
            
            print("✅ 初始化交换测试通过")
            
        finally:
            process.terminate()
            await process.wait()
    
    @pytest.mark.asyncio
    async def test_tools_round_trip(self, python_path, server_path):
        """测试3: 工具往返调用"""
        process = await asyncio.create_subprocess_exec(
            str(python_path), str(server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        try:
            # 跳过ready消息
            await self._read_response(process)
            
            # 初始化
            init_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }
            await self._send_message(process, init_msg)
            await self._read_response(process)  # 跳过初始化响应
            
            # 获取工具列表
            tools_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            await self._send_message(process, tools_msg)
            tools_response = await self._read_response(process)
            
            assert tools_response is not None
            assert "result" in tools_response
            assert "tools" in tools_response["result"]
            tools = tools_response["result"]["tools"]
            assert len(tools) > 0, "工具列表为空"
            
            # 调用第一个工具
            first_tool = tools[0]
            call_msg = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": first_tool["name"],
                    "arguments": {}
                }
            }
            
            await self._send_message(process, call_msg)
            call_response = await self._read_response(process)
            
            assert call_response is not None
            assert call_response.get("id") == 3
            assert "result" in call_response
            assert "content" in call_response["result"]
            
            print(f"✅ 工具往返调用测试通过 (工具: {first_tool['name']})")
            
        finally:
            process.terminate()
            await process.wait()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])