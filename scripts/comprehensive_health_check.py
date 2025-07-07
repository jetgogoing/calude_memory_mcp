#!/usr/bin/env python3
"""
Claude Memory综合健康检查
验证所有组件的健康状态和互连性
"""

import os
import time
import json
import psutil
import requests
import subprocess
import psycopg2
import sqlite3
from pathlib import Path
from datetime import datetime

class HealthChecker:
    """综合健康检查器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "components": {},
            "metrics": {},
            "recommendations": []
        }
    
    def check_system_resources(self):
        """检查系统资源"""
        print("🖥️ 检查系统资源...")
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            
            # 进程数量
            process_count = len(psutil.pids())
            
            system_status = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3),
                "process_count": process_count,
                "status": "healthy"
            }
            
            # 检查阈值
            issues = []
            if cpu_percent > 80:
                issues.append(f"CPU使用率过高: {cpu_percent:.1f}%")
            if memory.percent > 85:
                issues.append(f"内存使用率过高: {memory.percent:.1f}%")
            if disk.percent > 90:
                issues.append(f"磁盘使用率过高: {disk.percent:.1f}%")
            
            if issues:
                system_status["status"] = "warning"
                system_status["issues"] = issues
                self.results["recommendations"].extend([
                    "监控系统资源使用情况",
                    "考虑清理磁盘空间或增加系统资源"
                ])
            
            self.results["components"]["system"] = system_status
            print(f"✅ 系统资源: CPU {cpu_percent:.1f}%, 内存 {memory.percent:.1f}%, 磁盘 {disk.percent:.1f}%")
            
        except Exception as e:
            self.results["components"]["system"] = {
                "status": "error",
                "error": str(e)
            }
            print(f"❌ 系统资源检查失败: {e}")
    
    def check_postgresql(self):
        """检查PostgreSQL数据库"""
        print("🐘 检查PostgreSQL...")
        
        try:
            # 连接测试
            conn = psycopg2.connect(
                host="localhost",
                database="claude_memory_db",
                user="claude_memory",
                password="password",
                connect_timeout=5
            )
            
            cursor = conn.cursor()
            
            # 基本查询测试
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            # 获取数据库统计
            cursor.execute("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as db_size,
                    (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public') as table_count
            """)
            
            db_info = cursor.fetchone()
            
            # 检查表是否存在
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            # 检查数据量
            data_counts = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    data_counts[table] = cursor.fetchone()[0]
                except:
                    data_counts[table] = "无法访问"
            
            conn.close()
            
            postgres_status = {
                "status": "healthy",
                "database_size": db_info[0],
                "table_count": db_info[1],
                "tables": tables,
                "data_counts": data_counts,
                "connection_time_ms": "< 5000"
            }
            
            self.results["components"]["postgresql"] = postgres_status
            print(f"✅ PostgreSQL: {db_info[1]}张表, 大小 {db_info[0]}")
            
        except Exception as e:
            self.results["components"]["postgresql"] = {
                "status": "error",
                "error": str(e)
            }
            print(f"❌ PostgreSQL检查失败: {e}")
            self.results["recommendations"].append("检查PostgreSQL服务状态和连接配置")
    
    def check_qdrant(self):
        """检查Qdrant向量数据库"""
        print("🔍 检查Qdrant...")
        
        try:
            # 集群状态检查
            resp = requests.get("http://localhost:6333/cluster", timeout=5)
            if resp.status_code != 200:
                raise Exception(f"集群状态异常: {resp.status_code}")
            
            cluster_info = resp.json()
            
            # 集合列表检查
            resp = requests.get("http://localhost:6333/collections", timeout=5)
            if resp.status_code != 200:
                raise Exception(f"获取集合列表失败: {resp.status_code}")
            
            collections_info = resp.json()
            collections = collections_info.get("result", {}).get("collections", [])
            
            # 检查主要集合
            collection_details = {}
            for collection in collections:
                collection_name = collection["name"]
                try:
                    # 获取集合详情
                    resp = requests.get(f"http://localhost:6333/collections/{collection_name}", timeout=5)
                    if resp.status_code == 200:
                        details = resp.json()["result"]
                        
                        # 计算向量数量
                        count_resp = requests.post(
                            f"http://localhost:6333/collections/{collection_name}/points/count",
                            json={},
                            timeout=5
                        )
                        
                        if count_resp.status_code == 200:
                            count = count_resp.json()["result"]["count"]
                        else:
                            count = "未知"
                        
                        collection_details[collection_name] = {
                            "vectors_count": count,
                            "config": details.get("config", {}),
                            "status": details.get("status", "未知")
                        }
                except Exception as e:
                    collection_details[collection_name] = {"error": str(e)}
            
            qdrant_status = {
                "status": "healthy",
                "cluster_status": cluster_info,
                "collections_count": len(collections),
                "collections": collection_details
            }
            
            self.results["components"]["qdrant"] = qdrant_status
            print(f"✅ Qdrant: {len(collections)}个集合, 集群状态正常")
            
        except Exception as e:
            self.results["components"]["qdrant"] = {
                "status": "error", 
                "error": str(e)
            }
            print(f"❌ Qdrant检查失败: {e}")
            self.results["recommendations"].append("检查Qdrant服务状态和网络连接")
    
    def check_monitoring_services(self):
        """检查监控服务"""
        print("📊 检查监控服务...")
        
        monitoring_status = {}
        
        # Prometheus检查
        try:
            resp = requests.get("http://localhost:9090/-/healthy", timeout=5)
            if resp.status_code == 200:
                # 获取一些基本指标
                try:
                    targets_resp = requests.get("http://localhost:9090/api/v1/targets", timeout=5)
                    if targets_resp.status_code == 200:
                        targets_data = targets_resp.json()
                        active_targets = targets_data.get("data", {}).get("activeTargets", [])
                        
                        monitoring_status["prometheus"] = {
                            "status": "healthy",
                            "targets_count": len(active_targets),
                            "healthy_targets": len([t for t in active_targets if t.get("health") == "up"])
                        }
                    else:
                        monitoring_status["prometheus"] = {"status": "healthy", "details": "基本连接正常"}
                except:
                    monitoring_status["prometheus"] = {"status": "healthy", "details": "基本连接正常"}
                    
                print("✅ Prometheus: 服务正常")
            else:
                monitoring_status["prometheus"] = {"status": "error", "error": f"HTTP {resp.status_code}"}
                print(f"❌ Prometheus: HTTP {resp.status_code}")
        except Exception as e:
            monitoring_status["prometheus"] = {"status": "error", "error": str(e)}
            print(f"❌ Prometheus: {e}")
        
        # Alertmanager检查
        try:
            resp = requests.get("http://localhost:9093/-/healthy", timeout=5)
            if resp.status_code == 200:
                monitoring_status["alertmanager"] = {"status": "healthy"}
                print("✅ Alertmanager: 服务正常")
            else:
                monitoring_status["alertmanager"] = {"status": "error", "error": f"HTTP {resp.status_code}"}
                print(f"❌ Alertmanager: HTTP {resp.status_code}")
        except Exception as e:
            monitoring_status["alertmanager"] = {"status": "error", "error": str(e)}
            print(f"❌ Alertmanager: {e}")
        
        # Webhook服务检查
        try:
            test_payload = {"alerts": [{"status": "resolved", "labels": {"alertname": "test"}}]}
            resp = requests.post("http://localhost:8081/webhook", json=test_payload, timeout=5)
            if resp.status_code == 200:
                monitoring_status["webhook"] = {"status": "healthy"}
                print("✅ Alert Webhook: 服务正常")
            else:
                monitoring_status["webhook"] = {"status": "error", "error": f"HTTP {resp.status_code}"}
                print(f"❌ Alert Webhook: HTTP {resp.status_code}")
        except Exception as e:
            monitoring_status["webhook"] = {"status": "error", "error": str(e)}
            print(f"❌ Alert Webhook: {e}")
        
        self.results["components"]["monitoring"] = monitoring_status
    
    def check_mcp_server_functionality(self):
        """检查MCP服务器功能"""
        print("🔧 检查MCP服务器功能...")
        
        try:
            # 启动MCP服务器进程
            mcp_script = self.project_root / "monitoring_mcp_server.py"
            process = subprocess.Popen(
                ["python3", str(mcp_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root)
            )
            
            # 测试初始化
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}}
            }
            
            # 测试工具列表
            tools_request = {
                "jsonrpc": "2.0", 
                "id": 2,
                "method": "tools/list"
            }
            
            # 测试ping工具
            ping_request = {
                "jsonrpc": "2.0",
                "id": 3, 
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}}
            }
            
            # 发送请求序列
            input_data = "\n".join([
                json.dumps(init_request),
                json.dumps(tools_request), 
                json.dumps(ping_request)
            ]) + "\n"
            
            stdout, stderr = process.communicate(input=input_data, timeout=15)
            
            # 解析响应
            responses = []
            for line in stdout.strip().split('\n'):
                if line.strip():
                    try:
                        responses.append(json.loads(line))
                    except:
                        pass
            
            # 分析响应
            mcp_status = {
                "status": "healthy",
                "responses_count": len(responses),
                "tests_passed": []
            }
            
            # 检查初始化响应
            if any("serverInfo" in r.get("result", {}) for r in responses):
                mcp_status["tests_passed"].append("initialization")
            
            # 检查工具列表响应  
            if any("tools" in r.get("result", {}) for r in responses):
                mcp_status["tests_passed"].append("tools_list")
            
            # 检查ping响应
            if any("pong" in str(r.get("result", {})) for r in responses):
                mcp_status["tests_passed"].append("ping_tool")
            
            if len(mcp_status["tests_passed"]) >= 2:
                print(f"✅ MCP服务器: {len(mcp_status['tests_passed'])}项测试通过")
            else:
                mcp_status["status"] = "warning"
                print(f"⚠️ MCP服务器: 仅{len(mcp_status['tests_passed'])}项测试通过")
            
            self.results["components"]["mcp_server"] = mcp_status
            
        except subprocess.TimeoutExpired:
            process.kill()
            self.results["components"]["mcp_server"] = {
                "status": "error",
                "error": "MCP服务器响应超时"
            }
            print("❌ MCP服务器: 响应超时")
        except Exception as e:
            self.results["components"]["mcp_server"] = {
                "status": "error",
                "error": str(e)
            }
            print(f"❌ MCP服务器: {e}")
    
    def check_file_permissions_and_paths(self):
        """检查文件权限和路径"""
        print("📁 检查文件和权限...")
        
        file_status = {}
        
        # 关键文件检查
        critical_files = [
            ("MCP脚本", self.project_root / "monitoring_mcp_server.py"),
            ("数据库文件", self.project_root / "data" / "claude_memory.db"),
            ("Prometheus配置", self.project_root / "config" / "prometheus.yml"),
            ("Alertmanager配置", self.project_root / "config" / "alertmanager.yml"),
            ("Claude配置", Path.home() / ".claude.json")
        ]
        
        for name, path in critical_files:
            try:
                if path.exists():
                    stat = path.stat()
                    file_status[name] = {
                        "exists": True,
                        "readable": os.access(path, os.R_OK),
                        "writable": os.access(path, os.W_OK),
                        "executable": os.access(path, os.X_OK) if path.suffix == ".py" else "N/A",
                        "size_bytes": stat.st_size
                    }
                    print(f"✅ {name}: 存在且可访问")
                else:
                    file_status[name] = {"exists": False}
                    print(f"❌ {name}: 文件不存在")
            except Exception as e:
                file_status[name] = {"error": str(e)}
                print(f"❌ {name}: 检查失败 - {e}")
        
        # 关键目录检查
        critical_dirs = [
            ("日志目录", self.project_root / "logs"),
            ("报告目录", self.project_root / "reports"),
            ("备份目录", self.project_root / "backups"),
            ("数据目录", self.project_root / "data")
        ]
        
        for name, path in critical_dirs:
            try:
                if path.exists() and path.is_dir():
                    file_status[name] = {
                        "exists": True,
                        "writable": os.access(path, os.W_OK),
                        "files_count": len(list(path.iterdir())) if path.exists() else 0
                    }
                    print(f"✅ {name}: 存在且可写")
                else:
                    file_status[name] = {"exists": False}
                    print(f"❌ {name}: 目录不存在")
            except Exception as e:
                file_status[name] = {"error": str(e)}
                print(f"❌ {name}: 检查失败 - {e}")
        
        self.results["components"]["filesystem"] = file_status
    
    def calculate_overall_status(self):
        """计算总体健康状态"""
        component_statuses = []
        
        for component, status in self.results["components"].items():
            if isinstance(status, dict):
                comp_status = status.get("status", "unknown")
                component_statuses.append(comp_status)
        
        # 统计各状态数量
        healthy_count = component_statuses.count("healthy")
        warning_count = component_statuses.count("warning")
        error_count = component_statuses.count("error")
        total_count = len(component_statuses)
        
        # 计算总体状态
        if error_count == 0 and warning_count == 0:
            overall_status = "healthy"
        elif error_count == 0 and warning_count > 0:
            overall_status = "warning"
        elif error_count > 0 and healthy_count > error_count:
            overall_status = "degraded"
        else:
            overall_status = "critical"
        
        self.results["overall_status"] = overall_status
        self.results["metrics"] = {
            "total_components": total_count,
            "healthy_components": healthy_count,
            "warning_components": warning_count,
            "error_components": error_count,
            "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0
        }
        
        return overall_status
    
    def generate_report(self):
        """生成健康检查报告"""
        overall_status = self.calculate_overall_status()
        metrics = self.results["metrics"]
        
        print(f"\n📊 健康检查摘要:")
        print(f"总体状态: {overall_status.upper()}")
        print(f"组件总数: {metrics['total_components']}")
        print(f"健康组件: {metrics['healthy_components']}")
        print(f"警告组件: {metrics['warning_components']}")
        print(f"错误组件: {metrics['error_components']}")
        print(f"健康度: {metrics['health_percentage']:.1f}%")
        
        if self.results["recommendations"]:
            print(f"\n💡 建议:")
            for rec in self.results["recommendations"]:
                print(f"  • {rec}")
        
        # 保存详细报告
        report_file = self.project_root / "reports" / f"health_check_{int(time.time())}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存: {report_file}")
        
        return overall_status in ["healthy", "warning"]
    
    def run_full_health_check(self):
        """运行完整健康检查"""
        print("🏥 开始Claude Memory综合健康检查...")
        print("=" * 60)
        
        # 执行所有检查
        self.check_system_resources()
        self.check_postgresql()
        self.check_qdrant()
        self.check_monitoring_services()
        self.check_mcp_server_functionality()
        self.check_file_permissions_and_paths()
        
        # 生成报告
        success = self.generate_report()
        
        if success:
            print("\n🎉 健康检查完成！系统状态良好！")
        else:
            print("\n⚠️ 发现健康问题，请查看详细报告")
        
        return success

def main():
    """主函数"""
    checker = HealthChecker()
    return checker.run_full_health_check()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)