#!/usr/bin/env python3
"""
强制重新加载环境变量并进行测试
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 强制重新加载 .env 文件
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path, override=True)

# 打印环境变量确认
print("=== 环境变量检查 ===")
print(f"SILICONFLOW_API_KEY: {'✅ 已设置' if os.getenv('SILICONFLOW_API_KEY') else '❌ 未设置'}")
print(f"OPENROUTER_API_KEY: {'✅ 已设置' if os.getenv('OPENROUTER_API_KEY') else '❌ 未设置'}")
print(f"GEMINI_API_KEY: {'✅ 已设置' if os.getenv('GEMINI_API_KEY') else '❌ 未设置'}")
print()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入并运行主测试
from test_full_memory_injection import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())