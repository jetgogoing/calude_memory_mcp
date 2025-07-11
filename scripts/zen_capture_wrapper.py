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