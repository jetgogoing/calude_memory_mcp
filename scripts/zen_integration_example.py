#!/usr/bin/env python3
"""
ZEN MCP Server 集成示例
展示如何在 ZEN Server 中集成 AI 对话捕获
"""

from ai_conversation_hook import AIConversationCapture, capture_ai_conversation
import uuid
from typing import Dict, Any, Optional


class ZENServerIntegration:
    """ZEN Server 集成示例"""
    
    def __init__(self):
        # 初始化捕获器
        self.capture = AIConversationCapture(
            api_base_url="http://localhost:8000",
            project_id="zen-ai-conversations",
            enable_queue=True  # 启用队列，防止 API 故障时丢失数据
        )
        
        # 会话管理
        self.current_session_id = None
    
    def start_new_session(self) -> str:
        """开始新的会话"""
        self.current_session_id = str(uuid.uuid4())
        return self.current_session_id
    
    # 方法1：手动捕获
    async def call_ai_with_manual_capture(self, 
                                         agent_name: str,
                                         prompt: str,
                                         **kwargs) -> str:
        """手动捕获方式"""
        # 调用实际的 AI API
        response = await self._actual_ai_call(agent_name, prompt, **kwargs)
        
        # 捕获对话
        await self.capture.capture_conversation_async(
            input_text=prompt,
            output_text=response,
            metadata={
                "agent": agent_name,
                "task": kwargs.get("task", "general"),
                "temperature": kwargs.get("temperature", 0.7),
                "model": kwargs.get("model", "default")
            },
            session_id=self.current_session_id
        )
        
        return response
    
    # 方法2：使用装饰器
    async def call_ai_with_decorator(self, 
                                    agent_name: str,
                                    prompt: str,
                                    **kwargs) -> str:
        """装饰器方式"""
        
        # 为这个特定调用创建装饰器
        @self.capture.decorator(
            extract_input=lambda *a, **k: k.get('prompt', ''),
            extract_output=lambda result: result,
            metadata_func=lambda *a, **k: {
                "agent": k.get('agent_name', 'unknown'),
                "session_id": self.current_session_id,
                **k.get('metadata', {})
            }
        )
        async def wrapped_call(agent_name: str, prompt: str, **kwargs):
            return await self._actual_ai_call(agent_name, prompt, **kwargs)
        
        return await wrapped_call(
            agent_name=agent_name,
            prompt=prompt,
            metadata=kwargs
        )
    
    async def _actual_ai_call(self, agent_name: str, prompt: str, **kwargs) -> str:
        """模拟实际的 AI API 调用"""
        # 这里应该是实际调用 OpenAI/Claude/etc 的代码
        # 例如：
        # if agent_name == "openai":
        #     response = await openai_client.chat.completions.create(...)
        #     return response.choices[0].message.content
        
        # 模拟返回
        return f"[{agent_name}] Response to: {prompt[:50]}..."
    
    # 方法3：批量对话捕获
    async def capture_multi_turn_conversation(self, 
                                            turns: list,
                                            session_metadata: Dict[str, Any]):
        """捕获多轮对话"""
        session_id = str(uuid.uuid4())
        
        for turn in turns:
            await self.capture.capture_conversation_async(
                input_text=turn['input'],
                output_text=turn['output'],
                metadata={
                    **session_metadata,
                    "turn_number": turn.get('turn_number', 0),
                    "agent_from": turn.get('from_agent'),
                    "agent_to": turn.get('to_agent')
                },
                session_id=session_id
            )


# 使用环境变量控制是否启用捕获
import os

def create_zen_capture():
    """创建 ZEN 捕获器（可通过环境变量禁用）"""
    if os.getenv('DISABLE_AI_CAPTURE', '0') == '1':
        # 返回一个空操作的捕获器
        class DummyCapture:
            def capture_conversation(self, *args, **kwargs):
                return True
            
            def capture_conversation_async(self, *args, **kwargs):
                return True
            
            def decorator(self, *args, **kwargs):
                def dummy_decorator(func):
                    return func
                return dummy_decorator
        
        return DummyCapture()
    else:
        return AIConversationCapture(
            api_base_url=os.getenv('CLAUDE_MEMORY_API_URL', 'http://localhost:8000'),
            project_id=os.getenv('ZEN_PROJECT_ID', 'zen-ai-conversations')
        )


# 全局装饰器示例
zen_capture = create_zen_capture()

@zen_capture.decorator(
    extract_input=lambda messages, **_: messages[-1]['content'] if messages else '',
    extract_output=lambda response: response.choices[0].message.content if hasattr(response, 'choices') else str(response),
    metadata_func=lambda **kwargs: {
        "model": kwargs.get('model', 'unknown'),
        "temperature": kwargs.get('temperature', 0.7),
        "max_tokens": kwargs.get('max_tokens', 1000)
    }
)
async def call_openai_api(messages: list, **kwargs):
    """OpenAI API 调用示例"""
    # import openai
    # response = await openai.ChatCompletion.create(
    #     model=kwargs.get('model', 'gpt-4'),
    #     messages=messages,
    #     **kwargs
    # )
    # return response
    
    # 模拟返回
    return type('Response', (), {
        'choices': [type('Choice', (), {
            'message': type('Message', (), {
                'content': f"OpenAI response to: {messages[-1]['content'][:30]}..."
            })()
        })()]
    })()


# 测试代码
async def test_integration():
    """测试集成"""
    # 创建集成实例
    integration = ZENServerIntegration()
    
    # 开始新会话
    session_id = integration.start_new_session()
    print(f"Started session: {session_id}")
    
    # 测试手动捕获
    response1 = await integration.call_ai_with_manual_capture(
        agent_name="Claude",
        prompt="What is machine learning?",
        task="explanation"
    )
    print(f"Response 1: {response1}")
    
    # 测试装饰器捕获
    response2 = await integration.call_ai_with_decorator(
        agent_name="GPT-4",
        prompt="Explain quantum computing",
        task="explanation",
        temperature=0.5
    )
    print(f"Response 2: {response2}")
    
    # 测试全局装饰器
    messages = [
        {"role": "user", "content": "What is the meaning of life?"}
    ]
    response3 = await call_openai_api(messages, model="gpt-4", temperature=0.8)
    print(f"Response 3: {response3.choices[0].message.content}")
    
    # 测试批量捕获
    multi_turn = [
        {
            "input": "Agent A: Let's discuss AI safety",
            "output": "Agent B: Sure, AI safety is crucial...",
            "from_agent": "Agent-A",
            "to_agent": "Agent-B",
            "turn_number": 1
        },
        {
            "input": "Agent B: What specific aspects should we focus on?",
            "output": "Agent A: We should consider alignment, robustness...",
            "from_agent": "Agent-B", 
            "to_agent": "Agent-A",
            "turn_number": 2
        }
    ]
    
    await integration.capture_multi_turn_conversation(
        turns=multi_turn,
        session_metadata={
            "task": "ai_safety_discussion",
            "participants": ["Agent-A", "Agent-B"]
        }
    )
    print("Multi-turn conversation captured")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_integration())