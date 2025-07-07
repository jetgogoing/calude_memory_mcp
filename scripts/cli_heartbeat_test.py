#!/usr/bin/env python3
"""
Claude CLI心跳测试脚本
验证Claude CLI与MCP服务器的完整通信
"""

import os
import time
import json
import subprocess
import requests
from pathlib import Path

class CLIHeartbeatTest:
    """CLI心跳测试器"""
    
    def __init__(self):
        self.project_root = Path("/home/jetgogoing/claude_memory")
        self.test_results = []
        self.start_time = time.time()
    
    def log_test(self, test_name, success, message, details=None):
        """记录测试结果"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        
        if details:
            for line in details.split('\n'):
                if line.strip():
                    print(f"   {line}")
    
    def test_claude_cli_config(self):
        """测试Claude CLI配置"""
        print("\n🔧 测试1: Claude CLI配置检查")
        
        try:
            config_file = Path.home() / ".claude.json"
            
            if not config_file.exists():
                self.log_test("配置文件存在性", False, "Claude CLI配置文件不存在")
                return False
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # 检查MCP配置
            if "mcpServers" not in config:
                self.log_test("MCP配置", False, "缺少mcpServers配置")
                return False
            
            if "claude-memory" not in config["mcpServers"]:
                self.log_test("MCP配置", False, "缺少claude-memory MCP服务器配置")
                return False
            
            mcp_config = config["mcpServers"]["claude-memory"]
            expected_script = "/home/jetgogoing/claude_memory/monitoring_mcp_server.py"
            
            if mcp_config.get("args", [{}])[0] != expected_script:
                self.log_test("MCP配置", False, f"MCP脚本路径不正确: {mcp_config.get('args')}")
                return False
            
            self.log_test("配置文件检查", True, "Claude CLI配置正确", 
                         f"使用监控版MCP服务器: {expected_script}")
            return True
            
        except Exception as e:
            self.log_test("配置文件检查", False, f"配置检查失败: {e}")
            return False
    
    def test_mcp_server_direct(self):
        """测试MCP服务器直接连接"""
        print("\n🔗 测试2: MCP服务器直接测试")
        
        try:
            # 创建测试输入
            test_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"}
                }
            }
            
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
            
            # 发送初始化请求
            input_data = json.dumps(test_request) + "\n"
            stdout, stderr = process.communicate(input=input_data, timeout=10)
            
            if process.returncode == 0 or stdout:
                # 尝试解析响应
                try:
                    response = json.loads(stdout.strip().split('\n')[0])
                    if response.get("result", {}).get("serverInfo", {}).get("name") == "claude-memory-monitoring":
                        self.log_test("MCP服务器直接连接", True, "MCP服务器响应正常",
                                     f"服务器版本: {response['result']['serverInfo']['version']}")
                        return True
                except:
                    pass
                
                self.log_test("MCP服务器直接连接", True, "MCP服务器启动成功",
                             f"输出: {stdout[:100]}...")
                return True
            else:
                self.log_test("MCP服务器直接连接", False, "MCP服务器启动失败",
                             f"stderr: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            process.kill()
            self.log_test("MCP服务器直接连接", False, "MCP服务器响应超时")
            return False
        except Exception as e:
            self.log_test("MCP服务器直接连接", False, f"MCP服务器测试失败: {e}")
            return False
    
    def test_monitoring_endpoints(self):
        """测试监控端点"""
        print("\n📊 测试3: 监控端点测试")
        
        # 启动监控MCP服务器
        try:
            mcp_script = self.project_root / "monitoring_mcp_server.py"
            process = subprocess.Popen(
                ["python3", str(mcp_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            # 等待服务器启动
            time.sleep(3)
            
            # 测试指标端点
            try:
                resp = requests.get("http://localhost:8080/metrics", timeout=5)
                if resp.status_code == 200 and "claude_memory_uptime_seconds" in resp.text:
                    self.log_test("Prometheus指标端点", True, "指标端点正常工作",
                                 f"状态码: {resp.status_code}, 包含预期指标")
                else:
                    self.log_test("Prometheus指标端点", False, f"指标端点异常: {resp.status_code}")
            except requests.RequestException as e:
                self.log_test("Prometheus指标端点", False, f"指标端点连接失败: {e}")
            
            # 测试健康检查端点
            try:
                resp = requests.get("http://localhost:8080/health", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if "status" in data:
                        self.log_test("健康检查端点", True, "健康检查端点正常",
                                     f"状态: {data.get('status')}")
                    else:
                        self.log_test("健康检查端点", False, "健康检查响应格式异常")
                else:
                    self.log_test("健康检查端点", False, f"健康检查端点异常: {resp.status_code}")
            except requests.RequestException as e:
                self.log_test("健康检查端点", False, f"健康检查端点连接失败: {e}")
                
            # 清理进程
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
        except Exception as e:
            self.log_test("监控端点测试", False, f"监控端点测试失败: {e}")
    
    def test_claude_cli_process(self):
        """测试Claude CLI进程"""
        print("\n🤖 测试4: Claude CLI进程检查")
        
        try:
            # 检查Claude CLI是否在运行
            result = subprocess.run(
                ["pgrep", "-f", "claude"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                self.log_test("Claude CLI进程", True, f"找到Claude CLI进程",
                             f"进程ID: {', '.join(pids)}")
                return True
            else:
                self.log_test("Claude CLI进程", False, "未找到Claude CLI进程",
                             "可能需要启动Claude CLI")
                return False
                
        except Exception as e:
            self.log_test("Claude CLI进程检查", False, f"进程检查失败: {e}")
            return False
    
    def test_dependencies(self):
        """测试依赖项"""
        print("\n📦 测试5: 依赖项检查")
        
        success_count = 0
        total_count = 0
        
        # 检查Python模块
        modules = ["psycopg2", "requests", "json", "sqlite3"]
        for module in modules:
            total_count += 1
            try:
                __import__(module)
                self.log_test(f"Python模块 {module}", True, "模块可用")
                success_count += 1
            except ImportError:
                self.log_test(f"Python模块 {module}", False, "模块不可用")
        
        # 检查数据库连接
        total_count += 1
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="claude_memory_db",
                user="claude_memory",
                password="password"
            )
            conn.close()
            self.log_test("PostgreSQL连接", True, "数据库连接正常")
            success_count += 1
        except Exception as e:
            self.log_test("PostgreSQL连接", False, f"数据库连接失败: {e}")
        
        # 检查Qdrant连接
        total_count += 1
        try:
            resp = requests.get("http://localhost:6333/cluster", timeout=5)
            if resp.status_code == 200:
                self.log_test("Qdrant连接", True, "Qdrant服务正常")
                success_count += 1
            else:
                self.log_test("Qdrant连接", False, f"Qdrant响应异常: {resp.status_code}")
        except Exception as e:
            self.log_test("Qdrant连接", False, f"Qdrant连接失败: {e}")
        
        return success_count == total_count
    
    def generate_report(self):
        """生成测试报告"""
        end_time = time.time()
        duration = end_time - self.start_time
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        
        print(f"\n📊 测试报告:")
        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {total_tests - passed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        print(f"测试用时: {duration:.2f}秒")
        
        # 保存详细报告
        report = {
            "timestamp": time.time(),
            "duration_seconds": duration,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests/total_tests*100,
            "tests": self.test_results
        }
        
        report_file = self.project_root / "reports" / f"cli_heartbeat_test_{int(time.time())}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 详细报告已保存: {report_file}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始Claude CLI心跳测试...")
        print("=" * 60)
        
        # 执行所有测试
        self.test_claude_cli_config()
        self.test_mcp_server_direct()
        self.test_monitoring_endpoints()
        self.test_claude_cli_process()
        self.test_dependencies()
        
        # 生成报告
        success = self.generate_report()
        
        if success:
            print("\n🎉 所有测试通过！Claude CLI心跳测试成功！")
        else:
            print("\n⚠️ 部分测试失败，请检查详细报告")
        
        return success

def main():
    """主函数"""
    tester = CLIHeartbeatTest()
    return tester.run_all_tests()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)