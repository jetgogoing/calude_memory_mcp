#!/usr/bin/env python3
"""
快速集成脚本 - 最简单的方式在 ZEN Server 中添加 AI 对话捕获
只需要在 ZEN 的 AI 调用处添加几行代码
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path


# 简单的同步捕获函数
def capture_ai_conversation(input_text: str, 
                          output_text: str,
                          agent: str = "unknown",
                          task: str = "general",
                          session_id: str = None):
    """
    最简单的捕获函数，直接发送到 Claude Memory API
    
    使用方法：
    1. 在 ZEN Server 的 AI 调用后添加：
       response = call_ai_api(prompt)
       capture_ai_conversation(prompt, response, agent="GPT-4")
    """
    
    # 检查是否禁用
    if os.getenv('DISABLE_AI_CAPTURE', '0') == '1':
        return
    
    api_url = os.getenv('CLAUDE_MEMORY_API_URL', 'http://localhost:8000')
    
    try:
        # 构建请求
        payload = {
            "messages": [
                {"role": "user", "content": input_text},
                {"role": "assistant", "content": output_text}
            ],
            "project_id": "zen-ai-conversations",
            "title": f"AI-to-AI: {input_text[:50]}...",
            "metadata": {
                "agent": agent,
                "task": task,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        # 发送请求（60秒超时）
        response = requests.post(
            f"{api_url}/conversation/store",
            json=payload,
            timeout=60,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print(f"✓ AI conversation captured: {agent}")
        else:
            print(f"✗ Failed to capture: {response.status_code}")
            # 保存到本地队列
            _save_to_local_queue(payload)
            
    except Exception as e:
        print(f"✗ Error capturing conversation: {e}")
        # 保存到本地队列
        _save_to_local_queue({
            "input": input_text,
            "output": output_text,
            "agent": agent,
            "error": str(e)
        })


def _save_to_local_queue(data):
    """保存失败的请求到本地队列"""
    queue_dir = Path.home() / '.claude_memory' / 'ai_queue'
    queue_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    queue_file = queue_dir / f"failed_{timestamp}.json"
    
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# 异步版本（如果 ZEN 使用异步）
async def capture_ai_conversation_async(input_text: str,
                                      output_text: str, 
                                      agent: str = "unknown",
                                      task: str = "general",
                                      session_id: str = None):
    """异步版本的捕获函数"""
    import aiohttp
    
    if os.getenv('DISABLE_AI_CAPTURE', '0') == '1':
        return
    
    api_url = os.getenv('CLAUDE_MEMORY_API_URL', 'http://localhost:8000')
    
    try:
        payload = {
            "messages": [
                {"role": "user", "content": input_text},
                {"role": "assistant", "content": output_text}
            ],
            "project_id": "zen-ai-conversations",
            "title": f"AI-to-AI: {input_text[:50]}...",
            "metadata": {
                "agent": agent,
                "task": task,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/conversation/store",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    print(f"✓ AI conversation captured: {agent}")
                else:
                    print(f"✗ Failed to capture: {response.status}")
                    _save_to_local_queue(payload)
                    
    except Exception as e:
        print(f"✗ Error capturing conversation: {e}")
        _save_to_local_queue({
            "input": input_text,
            "output": output_text,
            "agent": agent,
            "error": str(e)
        })


# 示例：如何在 ZEN Server 中使用
"""
# 在 ZEN Server 的某个文件中：

from quick_zen_hook import capture_ai_conversation

# 原有的 AI 调用代码
async def call_claude_api(prompt: str) -> str:
    # ... 调用 Claude API ...
    response = await claude_client.messages.create(...)
    
    # 添加这一行来捕获对话
    capture_ai_conversation(
        input_text=prompt,
        output_text=response.content,
        agent="Claude",
        task="analysis"
    )
    
    return response.content

# 或者在多个 Agent 交互的地方
async def agent_conversation(agent_a_prompt: str) -> str:
    # Agent A 调用 Agent B
    agent_b_response = await call_agent_b(agent_a_prompt)
    capture_ai_conversation(
        agent_a_prompt, 
        agent_b_response,
        agent="AgentA->AgentB",
        session_id=current_session_id
    )
    
    # Agent B 的响应触发 Agent C
    agent_c_response = await call_agent_c(agent_b_response)
    capture_ai_conversation(
        agent_b_response,
        agent_c_response, 
        agent="AgentB->AgentC",
        session_id=current_session_id
    )
    
    return agent_c_response
"""


# 测试函数
def test_capture():
    """测试捕获功能"""
    print("Testing AI conversation capture...")
    
    # 测试简单捕获
    capture_ai_conversation(
        input_text="What is the capital of France?",
        output_text="The capital of France is Paris.",
        agent="Test-Agent",
        task="geography"
    )
    
    print("Test completed. Check Claude Memory API or queue directory.")


if __name__ == "__main__":
    test_capture()