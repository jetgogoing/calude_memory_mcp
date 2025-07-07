#!/usr/bin/env python3
"""
Claude Memory 全局服务健康检查脚本
用于Docker容器健康检查和系统监控
"""

import sys
import os
import json
import sqlite3
import requests
from pathlib import Path
from datetime import datetime
import logging

# 配置基本日志
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("healthcheck")


def check_global_database(db_path: str) -> dict:
    """检查全局数据库状态"""
    try:
        if not Path(db_path).exists():
            return {"status": "error", "message": f"数据库文件不存在: {db_path}"}
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'global_conversations', 'global_messages', 'project_metadata'
            )
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['global_conversations', 'global_messages', 'project_metadata']
        missing_tables = set(required_tables) - set(tables)
        
        if missing_tables:
            return {
                "status": "error", 
                "message": f"缺少必要表: {missing_tables}"
            }
        
        # 检查数据库连接和基本查询
        cursor.execute("SELECT COUNT(*) FROM global_conversations")
        conversation_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM global_messages")
        message_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "ok",
            "conversation_count": conversation_count,
            "message_count": message_count,
            "tables": tables
        }
        
    except Exception as e:
        return {"status": "error", "message": f"数据库检查失败: {str(e)}"}


def check_qdrant_connection(qdrant_url: str) -> dict:
    """检查Qdrant向量数据库连接"""
    try:
        # 尝试连接Qdrant
        response = requests.get(f"{qdrant_url}/health", timeout=5)
        if response.status_code == 200:
            # 检查集合
            collections_response = requests.get(f"{qdrant_url}/collections", timeout=5)
            if collections_response.status_code == 200:
                collections_data = collections_response.json()
                collections = [c["name"] for c in collections_data.get("result", {}).get("collections", [])]
                
                return {
                    "status": "ok",
                    "collections": collections,
                    "qdrant_version": response.headers.get("server", "unknown")
                }
            else:
                return {
                    "status": "warning",
                    "message": "Qdrant连接成功但无法获取集合信息"
                }
        else:
            return {
                "status": "error", 
                "message": f"Qdrant健康检查失败: HTTP {response.status_code}"
            }
    
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": f"无法连接到Qdrant: {qdrant_url}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Qdrant检查异常: {str(e)}"
        }


def check_global_directories() -> dict:
    """检查全局数据目录"""
    global_data_dir = Path.home() / ".claude-memory"
    required_dirs = [
        "data", "conversations", "vectors", 
        "cache", "logs", "config", "postgres", "qdrant"
    ]
    
    status = {"status": "ok", "directories": {}}
    
    for dir_name in required_dirs:
        dir_path = global_data_dir / dir_name
        if dir_path.exists():
            status["directories"][dir_name] = "exists"
        else:
            status["directories"][dir_name] = "missing"
            status["status"] = "warning"
    
    return status


def check_mcp_server_process() -> dict:
    """检查MCP服务器进程"""
    try:
        import psutil
        
        # 查找相关进程
        mcp_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(
                    'global_mcp_server.py' in ' '.join(proc.info['cmdline']),
                ):
                    mcp_processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cmdline": ' '.join(proc.info['cmdline'])
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if mcp_processes:
            return {
                "status": "ok",
                "processes": mcp_processes
            }
        else:
            return {
                "status": "warning",
                "message": "未找到运行中的MCP服务器进程"
            }
    
    except ImportError:
        return {
            "status": "warning",
            "message": "psutil未安装，无法检查进程状态"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"进程检查失败: {str(e)}"
        }


def main():
    """主健康检查函数"""
    # 读取环境变量配置
    global_data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
    db_path = global_data_dir / "global_memory.db"
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "service": "Claude Memory Global MCP Server",
        "version": "2.0.0",
        "overall_status": "ok"
    }
    
    # 检查全局目录
    dir_check = check_global_directories()
    health_report["directories"] = dir_check
    if dir_check["status"] != "ok":
        health_report["overall_status"] = "warning"
    
    # 检查数据库
    db_check = check_global_database(str(db_path))
    health_report["database"] = db_check
    if db_check["status"] == "error":
        health_report["overall_status"] = "error"
    
    # 检查Qdrant
    qdrant_check = check_qdrant_connection(qdrant_url)
    health_report["qdrant"] = qdrant_check
    if qdrant_check["status"] == "error":
        health_report["overall_status"] = "warning"  # Qdrant错误不影响核心功能
    
    # 检查进程
    process_check = check_mcp_server_process()
    health_report["processes"] = process_check
    
    # 输出结果
    print(json.dumps(health_report, ensure_ascii=False, indent=2))
    
    # Docker健康检查退出码
    if health_report["overall_status"] == "error":
        sys.exit(1)
    elif health_report["overall_status"] == "warning":
        sys.exit(0)  # 警告状态仍然认为健康
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()