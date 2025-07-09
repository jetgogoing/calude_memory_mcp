#!/usr/bin/env python3
"""
Claude Memory MCP服务 - 告警Webhook接收器

接收Alertmanager发送的告警并记录到日志文件。
支持按严重级别分类记录，并可扩展到其他通知渠道。
"""

import json
import os
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading
import logging
from pathlib import Path

class AlertWebhookHandler(BaseHTTPRequestHandler):
    """告警Webhook处理器"""
    
    def do_POST(self):
        """处理POST请求"""
        try:
            # 读取请求数据
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 解析JSON数据
            alert_data = json.loads(post_data.decode('utf-8'))
            
            # 获取告警级别
            path = urlparse(self.path).path
            if '/critical' in path:
                severity = 'CRITICAL'
                emoji = '🚨'
            elif '/warning' in path:
                severity = 'WARNING'
                emoji = '⚠️'
            elif '/info' in path:
                severity = 'INFO'
                emoji = 'ℹ️'
            else:
                severity = 'UNKNOWN'
                emoji = '📢'
            
            # 处理告警
            self.process_alerts(alert_data, severity, emoji)
            
            # 返回响应
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        except Exception as e:
            print(f"处理告警失败: {e}")
            self.send_response(500)
            self.end_headers()
    
    def process_alerts(self, alert_data, severity, emoji):
        """处理告警数据"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 写入告警日志
        log_file = "/home/jetgogoing/claude_memory/logs/alerts.log"
        
        with open(log_file, "a", encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{emoji} [{timestamp}] {severity} 告警\n")
            f.write(f"{'='*60}\n")
            
            # 处理每个告警
            for alert in alert_data.get('alerts', []):
                alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
                status = alert.get('status', 'unknown')
                
                f.write(f"📛 告警名称: {alert_name}\n")
                f.write(f"📊 状态: {status}\n")
                
                # 添加注释信息
                annotations = alert.get('annotations', {})
                if 'summary' in annotations:
                    f.write(f"📝 摘要: {annotations['summary']}\n")
                if 'description' in annotations:
                    f.write(f"📄 描述: {annotations['description']}\n")
                
                # 添加标签信息
                labels = alert.get('labels', {})
                if labels:
                    f.write("🏷️ 标签:\n")
                    for key, value in labels.items():
                        f.write(f"   {key}: {value}\n")
                
                # 添加时间信息
                if 'startsAt' in alert:
                    f.write(f"⏰ 开始时间: {alert['startsAt']}\n")
                if 'endsAt' in alert and alert['endsAt'] != '0001-01-01T00:00:00Z':
                    f.write(f"⏰ 结束时间: {alert['endsAt']}\n")
                
                f.write("-" * 40 + "\n")
            
            f.write(f"总计 {len(alert_data.get('alerts', []))} 个告警\n\n")
        
        # 打印到控制台
        print(f"{emoji} [{timestamp}] {severity}: 收到 {len(alert_data.get('alerts', []))} 个告警")
        for alert in alert_data.get('alerts', []):
            alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
            summary = alert.get('annotations', {}).get('summary', '')
            print(f"  - {alert_name}: {summary}")
    
    def log_message(self, format, *args):
        """禁用默认HTTP日志"""
        pass

def start_webhook_server():
    """启动Webhook服务器"""
    server_address = ('localhost', 8081)
    httpd = HTTPServer(server_address, AlertWebhookHandler)
    
    print(f"🎣 Claude Memory告警Webhook服务器启动在 http://localhost:8081")
    print("📝 告警日志将写入: /home/jetgogoing/claude_memory/logs/alerts.log")
    
    # 创建日志目录
    import os
    os.makedirs("/home/jetgogoing/claude_memory/logs", exist_ok=True)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Webhook服务器停止")
        httpd.shutdown()

if __name__ == "__main__":
    start_webhook_server()