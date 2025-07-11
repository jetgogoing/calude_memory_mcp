#!/usr/bin/env python3
"""极简版Claude包装器 - 仅捕获非交互模式"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

# 检查是否禁用
if os.environ.get('CLAUDE_MEMORY_DISABLE', '0') == '1':
    # 直接运行原始claude
    node_path = "/home/jetgogoing/.nvm/versions/node/v22.17.0/bin/node"
    claude_js = "/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js"
    os.execv(node_path, [node_path, claude_js] + sys.argv[1:])
    sys.exit(0)

# 队列目录
queue_dir = Path.home() / '.claude_memory' / 'queue'
queue_dir.mkdir(parents=True, exist_ok=True)

# 构建命令
node_path = "/home/jetgogoing/.nvm/versions/node/v22.17.0/bin/node"
claude_js = "/home/jetgogoing/.nvm/versions/node/v22.17.0/lib/node_modules/@anthropic-ai/claude-code/cli.js"
cmd = [node_path, claude_js] + sys.argv[1:]

# 检测是否是交互模式
is_interactive = len(sys.argv) == 1 or not any(arg for arg in sys.argv[1:] if not arg.startswith('-'))

if is_interactive:
    # 交互模式：直接运行
    os.execv(node_path, cmd)
else:
    # 非交互模式：捕获输出
    user_input = None
    for arg in sys.argv[1:]:
        if not arg.startswith('-') and arg:
            user_input = arg
            break
    
    # 运行命令
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # 输出到终端
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)
    
    # 保存对话
    if user_input and result.stdout:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        queue_file = queue_dir / f"conversation_{timestamp}.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input.strip(),
            'claude_response': result.stdout.strip()
        }
        
        with open(queue_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    sys.exit(result.returncode)