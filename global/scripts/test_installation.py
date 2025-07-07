#!/usr/bin/env python3
"""
Claude Memory MCP 全局服务安装测试脚本
验证所有组件正常工作，生成详细测试报告
"""

import os
import sys
import json
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InstallationTester:
    """安装测试器"""
    
    def __init__(self):
        self.test_results = {
            "start_time": datetime.now().isoformat(),
            "tests": {},
            "overall_success": False,
            "summary": {}
        }
        self.global_data_dir = Path.home() / ".claude-memory"
    
    def run_test(self, test_name: str, test_func) -> bool:
        """运行单个测试"""
        logger.info(f"运行测试: {test_name}")
        
        test_result = {
            "name": test_name,
            "success": False,
            "details": {},
            "errors": [],
            "warnings": [],
            "start_time": datetime.now().isoformat()
        }
        
        try:
            result = test_func()
            test_result["success"] = result.get("success", False)
            test_result["details"] = result.get("details", {})
            test_result["errors"] = result.get("errors", [])
            test_result["warnings"] = result.get("warnings", [])
            
            if test_result["success"]:
                logger.info(f"✓ {test_name} 通过")
            else:
                logger.error(f"✗ {test_name} 失败")
                
        except Exception as e:
            test_result["success"] = False
            test_result["errors"].append(f"测试执行异常: {str(e)}")
            logger.error(f"✗ {test_name} 异常: {e}")
        
        test_result["end_time"] = datetime.now().isoformat()
        self.test_results["tests"][test_name] = test_result
        
        return test_result["success"]
    
    def test_docker_services(self) -> Dict[str, Any]:
        """测试Docker服务"""
        result = {
            "success": False,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # 检查Docker是否安装
            docker_version = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if docker_version.returncode != 0:
                result["errors"].append("Docker未安装或无法访问")
                return result
            
            result["details"]["docker_version"] = docker_version.stdout.strip()
            
            # 检查容器状态
            container_ps = subprocess.run(
                ["docker", "ps", "--filter", "name=claude-memory-global", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if container_ps.returncode == 0:
                if "claude-memory-global" in container_ps.stdout:
                    result["details"]["container_status"] = "running"
                    result["details"]["container_info"] = container_ps.stdout.strip()
                else:
                    result["errors"].append("claude-memory-global容器未运行")
                    return result
            else:
                result["errors"].append(f"无法获取容器状态: {container_ps.stderr}")
                return result
            
            # 检查容器健康状态
            health_check = subprocess.run(
                ["docker", "exec", "claude-memory-global", "python", "/app/healthcheck.py"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if health_check.returncode == 0:
                try:
                    health_data = json.loads(health_check.stdout)
                    result["details"]["health_check"] = health_data
                    
                    if health_data.get("overall_status") == "ok":
                        result["success"] = True
                    else:
                        result["warnings"].append(f"健康检查状态: {health_data.get('overall_status')}")
                        result["success"] = True  # 警告不影响成功状态
                        
                except json.JSONDecodeError:
                    result["warnings"].append("健康检查输出格式无效")
            else:
                result["errors"].append(f"容器健康检查失败: {health_check.stderr}")
            
        except subprocess.TimeoutExpired:
            result["errors"].append("Docker命令执行超时")
        except FileNotFoundError:
            result["errors"].append("Docker命令未找到")
        except Exception as e:
            result["errors"].append(f"Docker测试异常: {str(e)}")
        
        return result
    
    def test_global_directories(self) -> Dict[str, Any]:
        """测试全局目录结构"""
        result = {
            "success": True,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        required_dirs = [
            "data", "logs", "config", "cache", "postgres", "qdrant"
        ]
        
        result["details"]["global_data_dir"] = str(self.global_data_dir)
        result["details"]["directories"] = {}
        
        if not self.global_data_dir.exists():
            result["errors"].append(f"全局数据目录不存在: {self.global_data_dir}")
            result["success"] = False
            return result
        
        for dir_name in required_dirs:
            dir_path = self.global_data_dir / dir_name
            if dir_path.exists():
                result["details"]["directories"][dir_name] = {
                    "exists": True,
                    "path": str(dir_path),
                    "permissions": oct(dir_path.stat().st_mode)[-3:]
                }
            else:
                result["details"]["directories"][dir_name] = {"exists": False}
                result["warnings"].append(f"目录不存在: {dir_name}")
        
        # 检查配置文件
        config_file = self.global_data_dir / "config" / "global_config.yml"
        if config_file.exists():
            result["details"]["config_file"] = {
                "exists": True,
                "size": config_file.stat().st_size
            }
        else:
            result["warnings"].append("全局配置文件不存在")
        
        return result
    
    def test_claude_cli_integration(self) -> Dict[str, Any]:
        """测试Claude CLI集成"""
        result = {
            "success": False,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # 检查Claude CLI安装
            claude_version = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if claude_version.returncode != 0:
                result["warnings"].append("Claude CLI未安装")
                result["success"] = True  # CLI不是必需的
                return result
            
            result["details"]["claude_version"] = claude_version.stdout.strip()
            
            # 检查配置文件
            if os.name == 'nt':  # Windows
                config_dir = Path(os.environ.get("APPDATA", "")) / "claude"
            else:
                config_dir = Path.home() / ".claude"
            
            config_file = config_dir / "claude.json"
            
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    result["details"]["config_file"] = {
                        "exists": True,
                        "path": str(config_file)
                    }
                    
                    # 检查MCP服务器配置
                    if "mcpServers" in config and "claude-memory-global" in config["mcpServers"]:
                        result["details"]["mcp_configured"] = True
                        result["success"] = True
                    else:
                        result["warnings"].append("MCP服务器未配置")
                        result["success"] = True
                        
                except json.JSONDecodeError:
                    result["errors"].append("Claude CLI配置文件格式无效")
            else:
                result["warnings"].append("Claude CLI配置文件不存在")
                result["success"] = True
            
            # 测试MCP命令
            if result["details"].get("mcp_configured"):
                try:
                    mcp_list = subprocess.run(
                        ["claude", "mcp", "list"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if mcp_list.returncode == 0:
                        if "claude-memory-global" in mcp_list.stdout:
                            result["details"]["mcp_service_listed"] = True
                            
                            # 测试ping
                            ping_test = subprocess.run(
                                ["claude", "mcp", "call", "claude-memory-global", "ping"],
                                capture_output=True,
                                text=True,
                                timeout=15
                            )
                            
                            if ping_test.returncode == 0:
                                result["details"]["ping_test"] = True
                                result["success"] = True
                            else:
                                result["warnings"].append(f"MCP ping测试失败: {ping_test.stderr}")
                        else:
                            result["warnings"].append("claude-memory-global未在MCP列表中")
                    else:
                        result["warnings"].append(f"MCP列表命令失败: {mcp_list.stderr}")
                        
                except subprocess.TimeoutExpired:
                    result["warnings"].append("MCP命令执行超时")
            
        except subprocess.TimeoutExpired:
            result["warnings"].append("Claude CLI命令超时")
        except FileNotFoundError:
            result["warnings"].append("Claude CLI未安装")
            result["success"] = True
        except Exception as e:
            result["errors"].append(f"Claude CLI测试异常: {str(e)}")
        
        return result
    
    def test_database_functionality(self) -> Dict[str, Any]:
        """测试数据库功能"""
        result = {
            "success": False,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # 测试数据库统计
            stats_cmd = subprocess.run(
                ["docker", "exec", "claude-memory-global", "python", "-c", """
import sys, os, json
sys.path.insert(0, '/app/src')
from global_mcp.global_memory_manager import GlobalMemoryManager
import asyncio
import yaml

try:
    with open('/app/config/global_config.yml', 'r') as f:
        config = yaml.safe_load(f)

    async def get_stats():
        manager = GlobalMemoryManager(config)
        return await manager.get_stats()

    result = asyncio.run(get_stats())
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({"error": str(e)}))
                """],
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if stats_cmd.returncode == 0:
                try:
                    stats_data = json.loads(stats_cmd.stdout)
                    if "error" in stats_data:
                        result["errors"].append(f"数据库统计获取失败: {stats_data['error']}")
                    else:
                        result["details"]["database_stats"] = stats_data
                        result["success"] = True
                        
                except json.JSONDecodeError:
                    result["errors"].append(f"数据库统计输出格式无效: {stats_cmd.stdout}")
            else:
                result["errors"].append(f"数据库统计命令失败: {stats_cmd.stderr}")
            
        except subprocess.TimeoutExpired:
            result["errors"].append("数据库测试命令超时")
        except Exception as e:
            result["errors"].append(f"数据库测试异常: {str(e)}")
        
        return result
    
    def test_mcp_tools(self) -> Dict[str, Any]:
        """测试MCP工具功能"""
        result = {
            "success": False,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        # 定义要测试的工具
        tools_to_test = [
            ("ping", "{}"),
            ("memory_status", "{}"),
            ("memory_health", "{}"),
            ("get_recent_conversations", '{"limit": 3}')
        ]
        
        result["details"]["tool_tests"] = {}
        successful_tools = 0
        
        for tool_name, args in tools_to_test:
            tool_result = {
                "success": False,
                "response_length": 0,
                "error": None
            }
            
            try:
                # 直接调用Docker容器中的MCP服务器
                tool_cmd = subprocess.run([
                    "docker", "exec", "claude-memory-global", 
                    "python", "-c", f"""
import sys, json, asyncio
sys.path.insert(0, '/app/src')
from global_mcp.global_mcp_server import GlobalMCPServer

async def test_tool():
    server = GlobalMCPServer()
    if hasattr(server, '{tool_name}'):
        try:
            args_dict = json.loads('{args}')
            result = await getattr(server, '{tool_name}')(args_dict)
            return {{"success": True, "result": result}}
        except Exception as e:
            return {{"success": False, "error": str(e)}}
    else:
        return {{"success": False, "error": "Tool not found"}}

result = asyncio.run(test_tool())
print(json.dumps(result))
                    """
                ], capture_output=True, text=True, timeout=15)
                
                if tool_cmd.returncode == 0:
                    try:
                        tool_response = json.loads(tool_cmd.stdout)
                        if tool_response.get("success"):
                            tool_result["success"] = True
                            tool_result["response_length"] = len(str(tool_response.get("result", "")))
                            successful_tools += 1
                        else:
                            tool_result["error"] = tool_response.get("error", "Unknown error")
                    except json.JSONDecodeError:
                        tool_result["error"] = f"Invalid JSON response: {tool_cmd.stdout}"
                else:
                    tool_result["error"] = f"Command failed: {tool_cmd.stderr}"
                    
            except subprocess.TimeoutExpired:
                tool_result["error"] = "Tool test timeout"
            except Exception as e:
                tool_result["error"] = f"Tool test exception: {str(e)}"
            
            result["details"]["tool_tests"][tool_name] = tool_result
        
        # 如果至少一半的工具测试成功，认为测试通过
        if successful_tools >= len(tools_to_test) // 2:
            result["success"] = True
        
        result["details"]["successful_tools"] = successful_tools
        result["details"]["total_tools"] = len(tools_to_test)
        
        return result
    
    def test_network_connectivity(self) -> Dict[str, Any]:
        """测试网络连接"""
        result = {
            "success": True,
            "details": {},
            "errors": [],
            "warnings": []
        }
        
        import socket
        
        # 测试端口
        ports_to_test = [
            (6334, "MCP服务端口"),
            (6335, "Qdrant向量数据库端口")
        ]
        
        result["details"]["port_tests"] = {}
        
        for port, description in ports_to_test:
            port_result = {"open": False, "description": description}
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    connection_result = sock.connect_ex(('localhost', port))
                    port_result["open"] = (connection_result == 0)
            except Exception as e:
                port_result["error"] = str(e)
            
            result["details"]["port_tests"][str(port)] = port_result
            
            if not port_result["open"] and port == 6334:
                result["warnings"].append(f"{description} ({port}) 不可访问")
        
        return result
    
    def run_all_tests(self) -> None:
        """运行所有测试"""
        logger.info("开始Claude Memory MCP安装测试...")
        
        # 定义测试列表
        tests = [
            ("全局目录结构", self.test_global_directories),
            ("Docker服务", self.test_docker_services),
            ("数据库功能", self.test_database_functionality),
            ("MCP工具", self.test_mcp_tools),
            ("网络连接", self.test_network_connectivity),
            ("Claude CLI集成", self.test_claude_cli_integration)
        ]
        
        successful_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                successful_tests += 1
        
        # 计算总体成功率
        success_rate = successful_tests / total_tests
        self.test_results["overall_success"] = success_rate >= 0.8  # 80%成功率
        
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate": f"{success_rate:.1%}"
        }
        
        self.test_results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"测试完成: {successful_tests}/{total_tests} 通过 ({success_rate:.1%})")
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report_lines = [
            "Claude Memory MCP 全局服务安装测试报告",
            "=" * 60,
            f"测试时间: {self.test_results['start_time']} - {self.test_results.get('end_time', 'N/A')}",
            f"总体结果: {'通过' if self.test_results['overall_success'] else '失败'}",
            "",
            "测试摘要:",
            f"  总测试数: {self.test_results['summary']['total_tests']}",
            f"  成功测试: {self.test_results['summary']['successful_tests']}",
            f"  失败测试: {self.test_results['summary']['failed_tests']}",
            f"  成功率: {self.test_results['summary']['success_rate']}",
            "",
            "详细测试结果:",
            "=" * 40
        ]
        
        for test_name, test_result in self.test_results["tests"].items():
            status = "✓ 通过" if test_result["success"] else "✗ 失败"
            report_lines.append(f"\n{test_name}: {status}")
            
            if test_result["details"]:
                report_lines.append("  详细信息:")
                for key, value in test_result["details"].items():
                    report_lines.append(f"    {key}: {value}")
            
            if test_result["warnings"]:
                report_lines.append("  警告:")
                for warning in test_result["warnings"]:
                    report_lines.append(f"    ⚠ {warning}")
            
            if test_result["errors"]:
                report_lines.append("  错误:")
                for error in test_result["errors"]:
                    report_lines.append(f"    ✗ {error}")
        
        # 添加建议
        if not self.test_results["overall_success"]:
            report_lines.extend([
                "",
                "故障排除建议:",
                "=" * 20,
                "1. 确保Docker服务正在运行",
                "2. 检查容器状态: docker ps | grep claude-memory",
                "3. 查看容器日志: docker logs claude-memory-global",
                "4. 重启服务: docker-compose -f docker-compose.global.yml restart",
                "5. 重新配置Claude CLI: ./scripts/configure_claude_cli.sh"
            ])
        
        return "\n".join(report_lines)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Memory MCP安装测试工具")
    parser.add_argument("--output", help="输出报告到文件")
    parser.add_argument("--json", action="store_true", help="输出JSON格式结果")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = InstallationTester()
    
    try:
        tester.run_all_tests()
        
        if args.json:
            # 输出JSON结果
            print(json.dumps(tester.test_results, indent=2, ensure_ascii=False))
        else:
            # 输出文本报告
            report = tester.generate_report()
            print(report)
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n报告已保存到: {args.output}")
        
        # 退出码
        sys.exit(0 if tester.test_results["overall_success"] else 1)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()