#!/bin/bash
# ZEN MCP Server AI 对话捕获自动安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查参数
if [ $# -ne 1 ]; then
    echo "Usage: $0 /path/to/zen-mcp-server"
    exit 1
fi

ZEN_DIR="$1"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLAUDE_MEMORY_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

print_info "Claude Memory 目录: $CLAUDE_MEMORY_DIR"
print_info "ZEN MCP Server 目录: $ZEN_DIR"

# 检查 ZEN 目录是否存在
if [ ! -d "$ZEN_DIR" ]; then
    print_error "ZEN MCP Server 目录不存在: $ZEN_DIR"
    exit 1
fi

# 检查是否是 ZEN MCP Server 项目
if [ ! -f "$ZEN_DIR/server.py" ] || [ ! -d "$ZEN_DIR/providers" ]; then
    print_error "指定的目录不是有效的 ZEN MCP Server 项目"
    exit 1
fi

# 创建必要的目录
print_info "创建必要的目录..."
mkdir -p "$ZEN_DIR/utils"

# 复制文件
print_info "复制 AI 对话捕获脚本..."
if [ -f "$CLAUDE_MEMORY_DIR/scripts/quick_zen_hook.py" ]; then
    cp "$CLAUDE_MEMORY_DIR/scripts/quick_zen_hook.py" "$ZEN_DIR/utils/ai_conversation_capture.py"
    print_info "✓ 复制 ai_conversation_capture.py"
else
    print_error "找不到 quick_zen_hook.py"
    exit 1
fi

# 创建 capture_wrapper.py
print_info "创建 capture_wrapper.py..."
cat > "$ZEN_DIR/providers/capture_wrapper.py" << 'EOF'
"""
AI Conversation Capture Wrapper for ZEN MCP Server
Automatically captures all AI-to-AI conversations
"""

import os
import logging
from typing import Optional, Dict, Any
from utils.ai_conversation_capture import capture_ai_conversation

logger = logging.getLogger(__name__)


class CaptureWrapper:
    """Wrapper to capture AI conversations from all providers"""
    
    def __init__(self, provider):
        """
        Initialize wrapper with a provider instance
        
        Args:
            provider: Any model provider (OpenAI, Gemini, etc.)
        """
        self.provider = provider
        self._capture_enabled = os.getenv('DISABLE_AI_CAPTURE', '0') != '1'
        
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        json_mode: bool = False,
        images: Optional[list[str]] = None,
        conversation_history: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Wrapper for generate_content that captures conversations
        """
        # Call the original method
        result = self.provider.generate_content(
            prompt=prompt,
            model_name=model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            json_mode=json_mode,
            images=images,
            conversation_history=conversation_history,
            metadata=metadata,
            **kwargs
        )
        
        # Capture the conversation if enabled
        if self._capture_enabled and result:
            try:
                # Extract the response content
                content = result.get('content', '')
                if content:
                    # Build full input (including system prompt if available)
                    full_input = prompt
                    if system_prompt:
                        full_input = f"System: {system_prompt}\n\nUser: {prompt}"
                    
                    # Prepare metadata
                    capture_metadata = {
                        "model": model_name,
                        "provider": self.provider.__class__.__name__,
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                        "json_mode": json_mode,
                        "has_images": bool(images),
                        "has_conversation_history": bool(conversation_history)
                    }
                    
                    # Add any additional metadata
                    if metadata:
                        capture_metadata.update(metadata)
                    
                    # Get session ID from metadata if available
                    session_id = capture_metadata.get('session_id')
                    
                    # Capture the conversation
                    capture_ai_conversation(
                        input_text=full_input,
                        output_text=content,
                        agent=f"{self.provider.__class__.__name__}/{model_name}",
                        task=capture_metadata.get('task', 'zen_ai_task'),
                        session_id=session_id
                    )
                    
                    logger.debug(f"Captured AI conversation: {model_name}")
                    
            except Exception as e:
                logger.error(f"Failed to capture AI conversation: {e}")
                # Don't fail the actual call, just log the error
        
        return result
    
    def __getattr__(self, name):
        """Forward all other attributes to the wrapped provider"""
        return getattr(self.provider, name)


def wrap_provider_with_capture(provider):
    """
    Convenience function to wrap any provider with capture functionality
    
    Args:
        provider: Model provider instance
        
    Returns:
        Wrapped provider with capture functionality
    """
    return CaptureWrapper(provider)
EOF

print_info "✓ 创建 capture_wrapper.py"

# 备份 registry.py
print_info "备份 registry.py..."
cp "$ZEN_DIR/providers/registry.py" "$ZEN_DIR/providers/registry.py.backup"
print_info "✓ 备份为 registry.py.backup"

# 修改 registry.py
print_info "修改 registry.py..."
TEMP_FILE=$(mktemp)

# 使用 Python 脚本进行精确修改
python3 << EOF > "$TEMP_FILE"
import re

with open("$ZEN_DIR/providers/registry.py", 'r') as f:
    content = f.read()

# 查找需要修改的位置
pattern = r'(\s+# Cache the instance\s+instance\._initialized_providers\[provider_type\] = provider\s+return provider)'

replacement = '''        # Wrap with capture functionality if enabled
        if os.getenv('DISABLE_AI_CAPTURE', '0') != '1':
            try:
                from .capture_wrapper import wrap_provider_with_capture
                provider = wrap_provider_with_capture(provider)
                logging.debug(f"Wrapped {provider_type} provider with AI conversation capture")
            except Exception as e:
                logging.warning(f"Failed to wrap provider with capture: {e}")
        
        # Cache the instance
        instance._initialized_providers[provider_type] = provider

        return provider'''

# 执行替换
modified = re.sub(pattern, replacement, content)

# 检查是否已经修改过
if 'wrap_provider_with_capture' in content:
    print("ALREADY_MODIFIED")
else:
    print(modified)
EOF

if [ "$(cat "$TEMP_FILE")" = "ALREADY_MODIFIED" ]; then
    print_warn "registry.py 已经修改过，跳过"
else
    cat "$TEMP_FILE" > "$ZEN_DIR/providers/registry.py"
    print_info "✓ 修改 registry.py"
fi

rm -f "$TEMP_FILE"

# 创建测试脚本
print_info "创建测试脚本..."
cat > "$ZEN_DIR/test_ai_capture.py" << 'EOF'
#!/usr/bin/env python3
"""
测试 AI 对话捕获功能
"""

import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 provider 和 registry
from providers.registry import ModelProviderRegistry
from providers.base import ProviderType

def test_capture():
    """测试 AI 对话捕获"""
    print("Testing AI conversation capture in ZEN MCP Server...")
    
    # 获取一个 provider (需要有对应的 API key)
    provider = None
    
    # 尝试获取 OpenAI provider
    if os.getenv("OPENAI_API_KEY"):
        provider = ModelProviderRegistry.get_provider(ProviderType.OPENAI)
        model_name = "gpt-3.5-turbo"
        print("Using OpenAI provider")
    
    # 尝试获取 Gemini provider
    elif os.getenv("GOOGLE_API_KEY"):
        provider = ModelProviderRegistry.get_provider(ProviderType.GOOGLE)
        model_name = "gemini-2.5-flash"
        print("Using Gemini provider")
    
    # 尝试获取 Custom provider (Ollama)
    elif os.getenv("CUSTOM_API_KEY") or os.getenv("CUSTOM_API_URL"):
        provider = ModelProviderRegistry.get_provider(ProviderType.CUSTOM)
        model_name = "llama3"
        print("Using Custom provider")
    
    if not provider:
        print("No provider available. Please set one of: OPENAI_API_KEY, GOOGLE_API_KEY, or CUSTOM_API_URL")
        return
    
    # 测试调用
    try:
        print(f"\nCalling {model_name} with test prompt...")
        result = provider.generate_content(
            prompt="What is the capital of France? Answer in one sentence.",
            model_name=model_name,
            temperature=0.7,
            metadata={
                "task": "test_capture",
                "session_id": "test-session-123"
            }
        )
        
        if result and result.get('content'):
            print(f"\nResponse: {result['content'][:100]}...")
            print("\n✓ AI call successful")
            print("✓ Conversation should be captured (check Claude Memory API or queue)")
        else:
            print("\n✗ No response received")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 确保不禁用捕获
    os.environ['DISABLE_AI_CAPTURE'] = '0'
    
    # 运行测试
    test_capture()
    
    print("\nTo check captured conversations:")
    print("1. Check API: curl http://localhost:8000/memory/search -X POST -H 'Content-Type: application/json' -d '{\"query\": \"France\", \"project_id\": \"zen-ai-conversations\"}'")
    print("2. Check queue: ls ~/.claude_memory/ai_queue/")
EOF

chmod +x "$ZEN_DIR/test_ai_capture.py"
print_info "✓ 创建测试脚本"

# 创建配置示例
print_info "创建配置示例..."
cat > "$ZEN_DIR/claude_memory_config.sh" << 'EOF'
#!/bin/bash
# Claude Memory 集成配置
# 在启动 ZEN MCP Server 前 source 此文件

# Claude Memory API 地址
export CLAUDE_MEMORY_API_URL="http://localhost:8000"

# 项目 ID（用于组织对话）
export ZEN_PROJECT_ID="zen-ai-conversations"

# 启用 AI 对话捕获（设为 1 禁用）
export DISABLE_AI_CAPTURE="0"

echo "Claude Memory integration configured:"
echo "  API URL: $CLAUDE_MEMORY_API_URL"
echo "  Project ID: $ZEN_PROJECT_ID"
echo "  Capture enabled: $([ "$DISABLE_AI_CAPTURE" = "0" ] && echo "Yes" || echo "No")"
EOF

chmod +x "$ZEN_DIR/claude_memory_config.sh"
print_info "✓ 创建配置示例"

# 完成
echo ""
print_info "==========================================="
print_info "ZEN MCP Server AI 对话捕获集成完成！"
print_info "==========================================="
echo ""
print_info "下一步："
echo ""
echo "1. 确保 Claude Memory API 正在运行："
echo "   cd $CLAUDE_MEMORY_DIR"
echo "   python -m claude_memory.api_server"
echo ""
echo "2. 配置环境变量（可选）："
echo "   source $ZEN_DIR/claude_memory_config.sh"
echo ""
echo "3. 测试集成："
echo "   cd $ZEN_DIR"
echo "   python test_ai_capture.py"
echo ""
print_info "文档：$CLAUDE_MEMORY_DIR/docs/ZEN_MCP_SERVER_INTEGRATION.md"