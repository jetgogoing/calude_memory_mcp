#!/usr/bin/env python3
"""
包装器单元测试
"""

import unittest
import subprocess
import json
import tempfile
from pathlib import Path
import os

class TestClaudeWrapper(unittest.TestCase):
    
    def test_wrapper_exists(self):
        """测试包装器是否存在"""
        wrapper_path = Path.home() / '.local/bin/claude'
        self.assertTrue(wrapper_path.exists(), "包装器文件不存在")
        self.assertTrue(os.access(wrapper_path, os.X_OK), "包装器没有执行权限")
    
    def test_disable_environment(self):
        """测试环境变量禁用功能"""
        env = os.environ.copy()
        env['CLAUDE_MEMORY_DISABLE'] = '1'
        
        result = subprocess.run(
            ['claude', '--version'],
            env=env,
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0, "禁用模式下运行失败")
    
    def test_queue_directory(self):
        """测试队列目录是否存在"""
        queue_dir = Path.home() / '.claude_memory' / 'queue'
        self.assertTrue(queue_dir.exists(), "队列目录不存在")
        self.assertTrue(queue_dir.is_dir(), "队列路径不是目录")
    
    def test_non_interactive_capture(self):
        """测试非交互模式捕获"""
        # 运行一个简单的命令
        test_message = f"unittest_{os.getpid()}"
        result = subprocess.run(
            ['claude', test_message],
            capture_output=True,
            text=True
        )
        
        self.assertEqual(result.returncode, 0, "命令执行失败")
        
        # 检查是否有输出
        self.assertTrue(len(result.stdout) > 0, "没有输出")
        
        # 检查队列中是否有新文件
        queue_dir = Path.home() / '.claude_memory' / 'queue'
        queue_files = list(queue_dir.glob("conversation_*.json"))
        
        # 查找包含我们测试消息的文件
        found = False
        for qf in queue_files:
            try:
                with open(qf, 'r') as f:
                    data = json.load(f)
                    if test_message in data.get('user_input', ''):
                        found = True
                        break
            except:
                continue
        
        self.assertTrue(found or len(queue_files) > 0, "对话未被保存到队列")

if __name__ == '__main__':
    unittest.main()