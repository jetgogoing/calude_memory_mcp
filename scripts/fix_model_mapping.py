#!/usr/bin/env python3
"""
修复模型映射问题的脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_model_configurations():
    """检查模型配置的一致性"""
    
    print("=== 检查 Claude Memory 系统的模型配置 ===\n")
    
    # 1. 检查 SemanticCompressor 中定义的模型
    from claude_memory.processors.semantic_compressor import SemanticCompressor
    compressor = SemanticCompressor()
    
    print("1. SemanticCompressor 中定义的模型：")
    print(f"   轻量级模型: {compressor.light_models}")
    print(f"   重量级模型: {compressor.heavy_models}")
    
    # 2. 检查 ModelManager 中的模型映射
    from claude_memory.utils.model_manager import ModelManager
    model_manager = ModelManager()
    
    print("\n2. ModelManager 中的模型映射：")
    for model, provider in model_manager.model_provider_map.items():
        print(f"   {model} -> {provider}")
    
    # 3. 检查未映射的模型
    print("\n3. 配置问题检查：")
    all_models = compressor.light_models + compressor.heavy_models
    missing_models = []
    
    for model in all_models:
        if model not in model_manager.model_provider_map:
            missing_models.append(model)
            print(f"   ❌ 模型 '{model}' 在 light_models/heavy_models 中定义，但未在 model_provider_map 中映射")
    
    if not missing_models:
        print("   ✅ 所有模型都已正确映射")
    
    # 4. 检查配置的提供商
    print("\n4. 配置的提供商和API密钥状态：")
    for provider, config in model_manager.providers.items():
        api_key_status = "✅ 已配置" if config['api_key'] else "❌ 未配置"
        print(f"   {provider}: {api_key_status}")
        print(f"      支持的模型: {config['models']}")
    
    # 5. 建议的修复
    if missing_models:
        print("\n5. 建议的修复方案：")
        print("\n   在 model_manager.py 的 model_provider_map 中添加：")
        for model in missing_models:
            # 猜测提供商
            if "deepseek" in model.lower():
                if "r1" in model:
                    # deepseek-r1 应该是 OpenRouter 提供的
                    suggested_provider = "openrouter"
                else:
                    suggested_provider = "siliconflow"
            elif "claude" in model.lower():
                suggested_provider = "openrouter"
            elif "gemini" in model.lower():
                suggested_provider = "gemini"
            else:
                suggested_provider = "unknown"
            
            print(f"   '{model}': '{suggested_provider}',")
        
        print("\n   或者，从 SemanticCompressor 的 light_models/heavy_models 中移除这些未映射的模型。")
    
    return missing_models


def suggest_fix():
    """提供修复建议"""
    
    print("\n\n=== 具体修复步骤 ===\n")
    
    print("1. 编辑 src/claude_memory/utils/model_manager.py")
    print("   在 model_provider_map 字典中添加：")
    print("   'deepseek-r1': 'openrouter',")
    print("   'claude-3.5-sonnet': 'openrouter',")
    print("\n2. 或者编辑 src/claude_memory/processors/semantic_compressor.py")
    print("   从 light_models 中移除 'deepseek-r1'")
    print("   从 heavy_models 中移除 'claude-3.5-sonnet'")
    print("\n3. 确保 OpenRouter API 密钥已配置（看起来已经配置了）")
    
    print("\n注意：'deepseek-r1' 可能需要通过 OpenRouter 访问，")
    print("      因为它不在 SiliconFlow 的模型列表中。")


if __name__ == "__main__":
    missing = check_model_configurations()
    if missing:
        suggest_fix()
    else:
        print("\n✅ 模型配置检查通过，无需修复。")