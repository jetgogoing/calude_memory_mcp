#!/usr/bin/env python3
"""测试包装器功能"""

import subprocess
import sys

# 直接运行claude命令
cmd = [sys.executable, "/home/jetgogoing/.local/bin/claude", "测试消息: Hello World"]
print(f"Running: {' '.join(cmd)}")

result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")