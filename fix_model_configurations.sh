#!/bin/bash
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
    sed -i 's/DEFAULT_EMBEDDING_MODEL=.*/DEFAULT_EMBEDDING_MODEL=Qwen\/Qwen3-Embedding-8B/g' $file
    sed -i 's/DEFAULT_RERANK_MODEL=.*/DEFAULT_RERANK_MODEL=Qwen\/Qwen3-Reranker-8B/g' $file
    sed -i 's/DEFAULT_LIGHT_MODEL=.*/DEFAULT_LIGHT_MODEL=deepseek-ai\/DeepSeek-V2.5/g' $file
    sed -i 's/MINI_LLM_PROVIDER_PRIORITY=.*/MINI_LLM_PROVIDER_PRIORITY=siliconflow,gemini,openrouter/g' $file
    sed -i 's/MEMORY_COMPRESSION_MODEL=.*/MEMORY_COMPRESSION_MODEL=deepseek-ai\/DeepSeek-V2.5/g' $file
    sed -i 's/MEMORY_FUSER_MODEL=.*/MEMORY_FUSER_MODEL=deepseek-ai\/DeepSeek-V2.5/g' $file
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
            f"\1\n            {mapping}  {comment}",
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
