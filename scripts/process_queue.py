#!/usr/bin/env python3
"""
处理失败队列中的对话记录
定期运行以重试失败的保存操作
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
import httpx
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class QueueProcessor:
    def __init__(self):
        self.queue_dir = Path.home() / '.claude_memory' / 'queue'
        self.mcp_endpoint = "http://localhost:8000"
        self.processed_dir = self.queue_dir / 'processed'
        self.processed_dir.mkdir(exist_ok=True)
        
    def process_all(self):
        """处理所有队列文件"""
        queue_files = list(self.queue_dir.glob('*.json'))
        
        if not queue_files:
            logger.info("队列为空")
            return
        
        logger.info(f"找到 {len(queue_files)} 个待处理文件")
        
        success_count = 0
        failed_count = 0
        
        for queue_file in queue_files:
            if self.process_file(queue_file):
                success_count += 1
            else:
                failed_count += 1
            
            # 避免过快请求
            time.sleep(0.5)
        
        logger.info(f"处理完成: 成功 {success_count}, 失败 {failed_count}")
    
    def process_file(self, queue_file: Path) -> bool:
        """处理单个队列文件"""
        try:
            # 读取数据
            with open(queue_file, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
            
            logger.info(f"处理: {queue_file.name}")
            
            # 构建请求
            url = f"{self.mcp_endpoint}/memory/conversation"
            
            # 准备对话数据
            payload = {
                'id': f"{conversation_data['session_id']}-{conversation_data['turn_number']}",
                'messages': [
                    {
                        'role': 'human',
                        'content': conversation_data['user_input']
                    },
                    {
                        'role': 'assistant', 
                        'content': conversation_data['claude_response']
                    }
                ],
                'metadata': conversation_data.get('metadata', {})
            }
            
            # 发送请求
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"✅ 成功保存: turn {conversation_data['turn_number']}")
                    
                    # 移动到已处理目录
                    processed_file = self.processed_dir / queue_file.name
                    queue_file.rename(processed_file)
                    
                    return True
                else:
                    logger.error(f"❌ API返回 {response.status_code}: {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"❌ 处理失败 {queue_file.name}: {e}")
            return False
    
    def check_mcp_health(self) -> bool:
        """检查MCP服务健康状态"""
        try:
            response = httpx.get(f"{self.mcp_endpoint}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def run_continuous(self, interval: int = 60):
        """持续运行模式"""
        logger.info(f"开始持续处理模式，间隔 {interval} 秒")
        
        while True:
            try:
                # 检查MCP服务
                if not self.check_mcp_health():
                    logger.warning("MCP服务不可用，等待下次重试...")
                else:
                    # 处理队列
                    self.process_all()
                
                # 等待下次处理
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("收到中断信号，退出...")
                break
            except Exception as e:
                logger.error(f"处理错误: {e}")
                time.sleep(interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='处理Claude Memory失败队列')
    parser.add_argument('--continuous', '-c', action='store_true', 
                      help='持续运行模式')
    parser.add_argument('--interval', '-i', type=int, default=60,
                      help='持续模式的检查间隔（秒）')
    
    args = parser.parse_args()
    
    processor = QueueProcessor()
    
    if args.continuous:
        processor.run_continuous(args.interval)
    else:
        processor.process_all()


if __name__ == '__main__':
    main()