#!/usr/bin/env python3
"""
队列处理服务 - 处理失败的对话保存请求
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import requests
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class QueueProcessor:
    """队列处理器"""
    
    def __init__(self):
        self.queue_dir = Path.home() / '.claude_memory' / 'queue'
        self.api_endpoint = "http://localhost:8000"
        
    def process_queue(self):
        """处理队列中的所有项目"""
        if not self.queue_dir.exists():
            logger.info("Queue directory does not exist")
            return
        
        queue_files = list(self.queue_dir.glob("conversation_*.json"))
        if not queue_files:
            logger.info("Queue is empty")
            return
        
        logger.info(f"Processing {len(queue_files)} items in queue")
        
        for queue_file in queue_files:
            try:
                # 读取队列文件
                with open(queue_file, 'r') as f:
                    data = json.load(f)
                
                # 准备API请求
                url = f"{self.api_endpoint}/conversation/store"
                payload = {
                    'messages': [
                        {
                            'role': 'user',
                            'content': data['user_input']
                        },
                        {
                            'role': 'assistant',
                            'content': data['claude_response']
                        }
                    ],
                    'project_id': 'global',
                    'title': f"CLI Session {data.get('timestamp', 'Unknown')}"
                }
                
                # 发送请求
                response = requests.post(url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    logger.info(f"Successfully processed: {queue_file.name}")
                    # 删除已处理的文件
                    queue_file.unlink()
                else:
                    logger.error(f"API error for {queue_file.name}: {response.status_code}")
                    logger.error(f"Response: {response.text}")
            
            except Exception as e:
                logger.error(f"Error processing {queue_file.name}: {e}")

def main():
    """主函数"""
    processor = QueueProcessor()
    processor.process_queue()

if __name__ == "__main__":
    main()