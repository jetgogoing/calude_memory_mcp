#!/usr/bin/env python3
"""
Claude Memory 状态监控脚本
"""

import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

def check_wrapper_status():
    """检查包装器状态"""
    result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
    wrapper_path = result.stdout.strip()
    
    return {
        'installed': wrapper_path.endswith('/.local/bin/claude'),
        'path': wrapper_path
    }

def check_api_status():
    """检查API服务状态"""
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        return {
            'running': response.status_code == 200,
            'status_code': response.status_code
        }
    except:
        return {
            'running': False,
            'status_code': None
        }

def check_queue_status():
    """检查队列状态"""
    queue_dir = Path.home() / '.claude_memory' / 'queue'
    if not queue_dir.exists():
        return {
            'exists': False,
            'count': 0,
            'oldest': None
        }
    
    queue_files = list(queue_dir.glob("conversation_*.json"))
    
    if queue_files:
        oldest_file = min(queue_files, key=lambda f: f.stat().st_mtime)
        oldest_age = datetime.now() - datetime.fromtimestamp(oldest_file.stat().st_mtime)
        
        return {
            'exists': True,
            'count': len(queue_files),
            'oldest': str(oldest_age).split('.')[0]
        }
    
    return {
        'exists': True,
        'count': 0,
        'oldest': None
    }

def get_recent_captures():
    """获取最近的捕获统计"""
    log_file = Path.home() / '.claude_memory' / 'wrapper_v2.log'
    if not log_file.exists():
        return {
            'today': 0,
            'last_hour': 0
        }
    
    today_count = 0
    hour_count = 0
    
    today = datetime.now().date()
    hour_ago = datetime.now() - timedelta(hours=1)
    
    # 简单统计（实际应用中可能需要更精确的日志解析）
    with open(log_file, 'r') as f:
        for line in f:
            if 'Captured conversation turn' in line:
                try:
                    # 解析时间戳
                    timestamp_str = line.split(']')[0][1:]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    
                    if timestamp.date() == today:
                        today_count += 1
                    if timestamp >= hour_ago:
                        hour_count += 1
                except:
                    continue
    
    return {
        'today': today_count,
        'last_hour': hour_count
    }

def print_status():
    """打印状态报告"""
    print("Claude Memory 监控报告")
    print("======================")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 包装器状态
    wrapper = check_wrapper_status()
    print("包装器状态:")
    print(f"  安装: {'✓' if wrapper['installed'] else '✗'}")
    print(f"  路径: {wrapper['path']}")
    print()
    
    # API状态
    api = check_api_status()
    print("API服务状态:")
    print(f"  运行: {'✓' if api['running'] else '✗'}")
    if api['status_code']:
        print(f"  响应: {api['status_code']}")
    print()
    
    # 队列状态
    queue = check_queue_status()
    print("队列状态:")
    print(f"  文件数: {queue['count']}")
    if queue['oldest']:
        print(f"  最旧文件: {queue['oldest']} 前")
    print()
    
    # 捕获统计
    captures = get_recent_captures()
    print("捕获统计:")
    print(f"  今日: {captures['today']} 条")
    print(f"  最近1小时: {captures['last_hour']} 条")
    print()
    
    # 健康评分
    health_score = 0
    if wrapper['installed']: health_score += 30
    if api['running']: health_score += 30
    if queue['count'] < 10: health_score += 20
    if captures['today'] > 0: health_score += 20
    
    print(f"健康评分: {health_score}/100")
    
    if health_score >= 80:
        print("状态: ✓ 优秀")
    elif health_score >= 60:
        print("状态: ⚠ 良好")
    else:
        print("状态: ✗ 需要检查")

if __name__ == '__main__':
    print_status()