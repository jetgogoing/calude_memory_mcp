#!/usr/bin/env python3
"""
Claude Memory 监控脚本
检查系统健康状态和性能指标
"""

import requests
import psycopg2
import time
import json
from datetime import datetime

def check_postgresql():
    """检查PostgreSQL状态"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="claude_memory_db",
            user="claude_memory", 
            password="password",
            connect_timeout=5
        )
        cur = conn.cursor()
        
        # 检查连接
        cur.execute("SELECT 1")
        
        # 检查表计数
        cur.execute("SELECT COUNT(*) FROM messages")
        message_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM conversations") 
        conversation_count = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "ok",
            "message_count": message_count,
            "conversation_count": conversation_count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_qdrant():
    """检查Qdrant状态"""
    try:
        # 集群状态
        resp = requests.get("http://localhost:6333/cluster", timeout=5)
        if resp.status_code != 200:
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
        
        # 向量计数
        resp = requests.post(
            "http://localhost:6333/collections/claude_memory_vectors_v14/points/count",
            json={}, timeout=5
        )
        count_data = resp.json()
        vector_count = count_data.get("result", {}).get("count", 0)
        
        return {
            "status": "ok", 
            "vector_count": vector_count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_mcp_server():
    """检查MCP服务器状态"""
    try:
        # 检查进程
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "mcp.*server"], 
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            return {"status": "ok", "processes": len(result.stdout.strip().split('\n'))}
        else:
            return {"status": "error", "error": "No MCP server processes found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def generate_report():
    """生成监控报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"🔍 Claude Memory 系统监控报告 - {timestamp}")
    print("=" * 60)
    
    # PostgreSQL检查
    pg_result = check_postgresql()
    if pg_result["status"] == "ok":
        print(f"✅ PostgreSQL: 正常 ({pg_result['message_count']} 消息, {pg_result['conversation_count']} 对话)")
    else:
        print(f"❌ PostgreSQL: 异常 - {pg_result['error']}")
    
    # Qdrant检查  
    qd_result = check_qdrant()
    if qd_result["status"] == "ok":
        print(f"✅ Qdrant: 正常 ({qd_result['vector_count']} 向量)")
    else:
        print(f"❌ Qdrant: 异常 - {qd_result['error']}")
    
    # MCP服务器检查
    mcp_result = check_mcp_server()
    if mcp_result["status"] == "ok":
        print(f"✅ MCP服务器: 正常 ({mcp_result['processes']} 进程)")
    else:
        print(f"❌ MCP服务器: 异常 - {mcp_result['error']}")
    
    # 总体状态
    all_ok = all(r["status"] == "ok" for r in [pg_result, qd_result, mcp_result])
    print("\n" + "=" * 60)
    print(f"🚀 系统总体状态: {'🟢 全部正常' if all_ok else '🔴 部分异常'}")
    
    # 保存监控数据
    monitor_data = {
        "timestamp": timestamp,
        "postgresql": pg_result,
        "qdrant": qd_result, 
        "mcp_server": mcp_result,
        "overall_status": "ok" if all_ok else "error"
    }
    
    with open("logs/monitoring.json", "w") as f:
        json.dump(monitor_data, f, indent=2)

if __name__ == "__main__":
    generate_report()