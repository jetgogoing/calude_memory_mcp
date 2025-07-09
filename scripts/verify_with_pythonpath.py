#!/usr/bin/env python3
"""
使用正确的Python路径运行验证脚本
"""

import subprocess
import sys
from pathlib import Path

# 设置项目根目录
project_root = Path(__file__).parent.parent

# 运行验证脚本
cmd = [
    sys.executable,
    str(project_root / "scripts" / "verify_model_configurations.py")
]

# 设置环境变量
env = {
    'PYTHONPATH': str(project_root),
    'PATH': '/usr/bin:/bin'
}

# 加载.env文件中的环境变量
env_file = project_root / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()

# 运行验证
result = subprocess.run(cmd, env=env)
sys.exit(result.returncode)