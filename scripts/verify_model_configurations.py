#!/usr/bin/env python3
"""
深度验证 Claude Memory 系统的模型配置一致性
确保所有模块使用统一的配置
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class ModelConfigurationVerifier:
    """模型配置验证器"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        
        # 用户指定的正确配置
        self.expected_config = {
            # 嵌入和重排序模型 (SiliconFlow)
            'embedding_model': 'Qwen/Qwen3-Embedding-8B',
            'rerank_model': 'Qwen/Qwen3-Reranker-8B',
            
            # Mini LLM 模型 (优先顺序: siliconflow → gemini → openrouter)
            'mini_llm_models': {
                'siliconflow': 'deepseek-ai/DeepSeek-V2.5',
                'gemini': 'gemini-2.5-flash',
                'openrouter': 'deepseek/deepseek-chat-v3-0324'
            },
            'provider_priority': ['siliconflow', 'gemini', 'openrouter'],
            
            # 提供商的可用模型
            'provider_models': {
                'siliconflow': [
                    'deepseek-ai/DeepSeek-V2.5',
                    'deepseek-ai/DeepSeek-V3',
                    'Qwen/Qwen3-Embedding-8B',
                    'Qwen/Qwen3-Reranker-8B',
                    'Qwen/Qwen2.5-1.5B-Instruct'
                ],
                'gemini': [
                    'gemini-2.5-pro',
                    'gemini-2.5-flash',
                    'text-embedding-004'
                ],
                'openrouter': [
                    'deepseek/deepseek-chat-v3-0324',
                    'anthropic/claude-3.5-sonnet',
                    'openai/gpt-4'
                ]
            }
        }
    
    def verify_env_files(self):
        """验证所有环境变量文件的一致性"""
        print("\n=== 1. 验证环境变量文件配置 ===\n")
        
        env_files = ['.env', '.env.example', '.env.docker.example']
        required_vars = {
            'SILICONFLOW_API_KEY': 'SiliconFlow API密钥',
            'GEMINI_API_KEY': 'Gemini API密钥',
            'OPENROUTER_API_KEY': 'OpenRouter API密钥',
            'DEFAULT_EMBEDDING_MODEL': 'Qwen/Qwen3-Embedding-8B',
            'DEFAULT_RERANK_MODEL': 'Qwen/Qwen3-Reranker-8B',
            'DEFAULT_LIGHT_MODEL': 'deepseek-ai/DeepSeek-V2.5',
            'MINI_LLM_ENABLED': 'true',
            'MINI_LLM_PROVIDER_PRIORITY': 'siliconflow,gemini,openrouter',
            'MEMORY_COMPRESSION_MODEL': 'deepseek-ai/DeepSeek-V2.5',
            'MEMORY_FUSER_MODEL': 'deepseek-ai/DeepSeek-V2.5'
        }
        
        for env_file in env_files:
            env_path = Path(env_file)
            if not env_path.exists():
                self.warnings.append(f"环境文件不存在: {env_file}")
                continue
            
            print(f"检查 {env_file}:")
            env_vars = {}
            
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
            
            # 检查必需的变量
            for var, expected in required_vars.items():
                if var in env_vars:
                    actual = env_vars[var]
                    if var.endswith('_API_KEY'):
                        if actual:
                            print(f"  ✅ {var}: 已设置")
                        else:
                            self.issues.append(f"{env_file}: {var} 为空")
                            print(f"  ❌ {var}: 未设置")
                    else:
                        if actual == expected:
                            print(f"  ✅ {var}: {actual}")
                        else:
                            self.issues.append(f"{env_file}: {var} 应为 '{expected}'，实际为 '{actual}'")
                            print(f"  ❌ {var}: 期望 '{expected}'，实际 '{actual}'")
                else:
                    self.issues.append(f"{env_file}: 缺少 {var}")
                    print(f"  ❌ {var}: 缺失")
    
    def verify_settings_py(self):
        """验证 settings.py 中的配置"""
        print("\n=== 2. 验证 settings.py 配置 ===\n")
        
        try:
            from claude_memory.config.settings import get_settings
            settings = get_settings()
            
            # 检查模型设置
            checks = [
                ('默认嵌入模型', settings.models.default_embedding_model, self.expected_config['embedding_model']),
                ('默认重排序模型', settings.models.default_rerank_model, self.expected_config['rerank_model']),
                ('默认轻量模型', settings.models.default_light_model, self.expected_config['mini_llm_models']['siliconflow']),
                ('Mini LLM启用', settings.mini_llm.enabled, True),
                ('提供商优先级', settings.mini_llm.provider_priority, 'siliconflow,gemini,openrouter'),
                ('SiliconFlow模型', settings.mini_llm.siliconflow_model, self.expected_config['mini_llm_models']['siliconflow']),
                ('Gemini模型', settings.mini_llm.gemini_model, self.expected_config['mini_llm_models']['gemini']),
                ('OpenRouter模型', settings.mini_llm.openrouter_model, self.expected_config['mini_llm_models']['openrouter'])
            ]
            
            for name, actual, expected in checks:
                if str(actual) == str(expected):
                    print(f"✅ {name}: {actual}")
                    self.successes.append(f"settings.py: {name} 配置正确")
                else:
                    print(f"❌ {name}: 期望 '{expected}'，实际 '{actual}'")
                    self.issues.append(f"settings.py: {name} 配置错误")
            
            # 检查API密钥
            api_keys = [
                ('SiliconFlow', settings.models.siliconflow_api_key),
                ('Gemini', settings.models.gemini_api_key),
                ('OpenRouter', settings.models.openrouter_api_key)
            ]
            
            print("\nAPI密钥状态:")
            for name, key in api_keys:
                if key:
                    print(f"✅ {name} API密钥: 已配置")
                else:
                    print(f"❌ {name} API密钥: 未配置")
                    self.issues.append(f"settings.py: {name} API密钥未配置")
                    
        except Exception as e:
            self.issues.append(f"无法加载 settings.py: {str(e)}")
            print(f"❌ 加载设置失败: {str(e)}")
    
    def verify_model_manager(self):
        """验证 ModelManager 中的模型映射"""
        print("\n=== 3. 验证 ModelManager 模型映射 ===\n")
        
        try:
            from claude_memory.utils.model_manager import ModelManager
            model_manager = ModelManager()
            
            # 检查所有必需的模型是否都有映射
            required_models = [
                'Qwen/Qwen3-Embedding-8B',
                'Qwen/Qwen3-Reranker-8B',
                'deepseek-ai/DeepSeek-V2.5',
                'gemini-2.5-flash',
                'gemini-2.5-pro',
                'deepseek/deepseek-chat-v3-0324'
            ]
            
            print("模型映射检查:")
            for model in required_models:
                if model in model_manager.model_provider_map:
                    provider = model_manager.model_provider_map[model]
                    print(f"✅ {model} -> {provider}")
                else:
                    print(f"❌ {model}: 未找到映射")
                    self.issues.append(f"ModelManager: {model} 未映射到任何提供商")
            
            # 检查提供商配置
            print("\n提供商配置:")
            for provider, config in model_manager.providers.items():
                api_key_status = "已配置" if config['api_key'] else "未配置"
                print(f"{provider}: API密钥 {api_key_status}")
                print(f"  支持的模型: {', '.join(config['models'])}")
                
        except Exception as e:
            self.issues.append(f"无法加载 ModelManager: {str(e)}")
            print(f"❌ 加载 ModelManager 失败: {str(e)}")
    
    def verify_semantic_compressor(self):
        """验证 SemanticCompressor 中的模型配置"""
        print("\n=== 4. 验证 SemanticCompressor 配置 ===\n")
        
        try:
            from claude_memory.processors.semantic_compressor import SemanticCompressor
            compressor = SemanticCompressor()
            
            print("轻量级模型:")
            for model in compressor.light_models:
                print(f"  - {model}")
                if model == 'deepseek-r1':
                    self.warnings.append("SemanticCompressor: 'deepseek-r1' 可能需要映射到正确的提供商")
            
            print("\n重量级模型:")
            for model in compressor.heavy_models:
                print(f"  - {model}")
                if model == 'claude-3.5-sonnet':
                    self.warnings.append("SemanticCompressor: 'claude-3.5-sonnet' 需要完整的模型名称")
                    
        except Exception as e:
            self.issues.append(f"无法加载 SemanticCompressor: {str(e)}")
            print(f"❌ 加载 SemanticCompressor 失败: {str(e)}")
    
    async def verify_mini_llm_manager(self):
        """验证 MiniLLMManager 的运行时配置"""
        print("\n=== 5. 验证 MiniLLMManager 运行时配置 ===\n")
        
        try:
            from claude_memory.llm.mini_llm_manager import MiniLLMManager, TaskType
            manager = MiniLLMManager()
            await manager.initialize()
            
            # 检查路由规则
            print("任务路由规则:")
            for task_type, rules in manager.task_router.routing_rules.items():
                if task_type == TaskType.COMPLETION:
                    print(f"\n{task_type}:")
                    print(f"  首选模型: {rules.get('preferred_model')}")
                    print(f"  提供商优先级: {rules.get('provider_priority')}")
                    
                    # 验证COMPLETION任务使用正确的配置
                    expected_priority = self.expected_config['provider_priority']
                    actual_priority = rules.get('provider_priority', [])
                    
                    if actual_priority == expected_priority:
                        self.successes.append("MiniLLMManager: COMPLETION任务优先级配置正确")
                    else:
                        self.issues.append(f"MiniLLMManager: COMPLETION任务优先级错误 - 期望{expected_priority}，实际{actual_priority}")
            
            # 检查可用的提供商
            print("\n已初始化的提供商:")
            for provider, instance in manager.providers.items():
                is_available = await instance.is_available()
                status = "可用" if is_available else "不可用"
                print(f"  {provider}: {status}")
                if not is_available:
                    self.warnings.append(f"MiniLLMManager: {provider} 提供商不可用")
            
            await manager.cleanup()
            
        except Exception as e:
            self.issues.append(f"无法验证 MiniLLMManager: {str(e)}")
            print(f"❌ 验证 MiniLLMManager 失败: {str(e)}")
    
    async def verify_api_connectivity(self):
        """验证API连接性"""
        print("\n=== 6. 验证API连接性 ===\n")
        
        try:
            from claude_memory.utils.model_manager import ModelManager
            from claude_memory.llm.mini_llm_manager import (
                MiniLLMManager, MiniLLMRequest, TaskType
            )
            
            # 测试嵌入生成
            print("测试嵌入生成 (Qwen3-Embedding-8B):")
            model_manager = ModelManager()
            await model_manager.initialize()
            
            try:
                response = await model_manager.generate_embedding(
                    model="Qwen/Qwen3-Embedding-8B",
                    text="测试文本"
                )
                print(f"✅ 嵌入维度: {response.dimension}")
                self.successes.append("API连接: Qwen3嵌入生成成功")
            except Exception as e:
                print(f"❌ 嵌入生成失败: {str(e)}")
                self.issues.append(f"API连接: Qwen3嵌入生成失败 - {str(e)}")
            
            # 测试Mini LLM
            print("\n测试Mini LLM (DeepSeek-V2.5):")
            mini_llm = MiniLLMManager()
            await mini_llm.initialize()
            
            try:
                request = MiniLLMRequest(
                    task_type=TaskType.COMPLETION,
                    input_text="Hello, this is a test.",
                    parameters={"max_tokens": 50}
                )
                response = await mini_llm.process(request)
                print(f"✅ 使用模型: {response.model_used}")
                print(f"✅ 提供商: {response.provider}")
                self.successes.append(f"API连接: Mini LLM通过{response.provider}成功")
            except Exception as e:
                print(f"❌ Mini LLM调用失败: {str(e)}")
                self.issues.append(f"API连接: Mini LLM调用失败 - {str(e)}")
            
            await model_manager.close()
            await mini_llm.cleanup()
            
        except Exception as e:
            self.issues.append(f"API连接测试失败: {str(e)}")
            print(f"❌ API连接测试失败: {str(e)}")
    
    def generate_fix_script(self):
        """生成修复脚本"""
        if not self.issues:
            return
        
        print("\n=== 生成修复脚本 ===\n")
        
        fix_script = """#!/bin/bash
# Claude Memory 模型配置修复脚本
# 生成时间: $(date)

echo "开始修复模型配置..."

# 1. 更新环境变量文件
update_env_file() {
    local file=$1
    echo "更新 $file..."
    
    # 备份原文件
    cp $file ${file}.backup.$(date +%Y%m%d_%H%M%S)
    
    # 更新模型配置
    sed -i 's/DEFAULT_EMBEDDING_MODEL=.*/DEFAULT_EMBEDDING_MODEL=Qwen\\/Qwen3-Embedding-8B/g' $file
    sed -i 's/DEFAULT_RERANK_MODEL=.*/DEFAULT_RERANK_MODEL=Qwen\\/Qwen3-Reranker-8B/g' $file
    sed -i 's/DEFAULT_LIGHT_MODEL=.*/DEFAULT_LIGHT_MODEL=deepseek-ai\\/DeepSeek-V2.5/g' $file
    sed -i 's/MINI_LLM_PROVIDER_PRIORITY=.*/MINI_LLM_PROVIDER_PRIORITY=siliconflow,gemini,openrouter/g' $file
    sed -i 's/MEMORY_COMPRESSION_MODEL=.*/MEMORY_COMPRESSION_MODEL=deepseek-ai\\/DeepSeek-V2.5/g' $file
    sed -i 's/MEMORY_FUSER_MODEL=.*/MEMORY_FUSER_MODEL=deepseek-ai\\/DeepSeek-V2.5/g' $file
}

# 更新所有环境文件
for env_file in .env .env.example .env.docker.example; do
    if [ -f "$env_file" ]; then
        update_env_file $env_file
    fi
done

echo "✅ 环境变量文件更新完成"

# 2. 修复Python代码中的模型映射
echo "修复模型映射..."

# 在model_manager.py中添加缺失的映射
python3 << 'EOF'
import re
from pathlib import Path

model_manager_path = Path("src/claude_memory/utils/model_manager.py")
content = model_manager_path.read_text()

# 确保所有模型都有正确的映射
mappings_to_add = {
    "'deepseek-r1': 'openrouter',": "# deepseek-r1 映射到 openrouter",
    "'claude-3.5-sonnet': 'openrouter',": "# 简短名称映射"
}

for mapping, comment in mappings_to_add.items():
    if mapping not in content:
        # 在model_provider_map字典中添加
        content = re.sub(
            r"(self\.model_provider_map = {[^}]+)",
            f"\\1\\n            {mapping}  {comment}",
            content,
            flags=re.DOTALL
        )

model_manager_path.write_text(content)
print("✅ model_manager.py 更新完成")
EOF

echo "✅ 所有修复完成！"
echo ""
echo "请重新启动服务以应用更改："
echo "  docker-compose restart"
echo "  或"
echo "  python -m claude_memory"
"""
        
        with open('fix_model_configurations.sh', 'w') as f:
            f.write(fix_script)
        
        os.chmod('fix_model_configurations.sh', 0o755)
        print("已生成修复脚本: fix_model_configurations.sh")
        print("执行命令: ./fix_model_configurations.sh")
    
    def print_summary(self):
        """打印验证摘要"""
        print("\n" + "="*60)
        print("验证摘要")
        print("="*60)
        
        print(f"\n✅ 成功项: {len(self.successes)}")
        for success in self.successes[:5]:  # 只显示前5个
            print(f"  - {success}")
        if len(self.successes) > 5:
            print(f"  ... 还有 {len(self.successes) - 5} 项")
        
        print(f"\n⚠️  警告项: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"  - {warning}")
        
        print(f"\n❌ 问题项: {len(self.issues)}")
        for issue in self.issues:
            print(f"  - {issue}")
        
        if not self.issues:
            print("\n🎉 恭喜！所有模型配置都已统一，符合要求。")
        else:
            print("\n⚠️  发现配置不一致，请运行生成的修复脚本。")


async def main():
    """主函数"""
    print("="*60)
    print("Claude Memory 模型配置深度验证")
    print("="*60)
    
    verifier = ModelConfigurationVerifier()
    
    # 执行所有验证
    verifier.verify_env_files()
    verifier.verify_settings_py()
    verifier.verify_model_manager()
    verifier.verify_semantic_compressor()
    await verifier.verify_mini_llm_manager()
    await verifier.verify_api_connectivity()
    
    # 打印摘要
    verifier.print_summary()
    
    # 生成修复脚本
    if verifier.issues:
        verifier.generate_fix_script()


if __name__ == "__main__":
    asyncio.run(main())