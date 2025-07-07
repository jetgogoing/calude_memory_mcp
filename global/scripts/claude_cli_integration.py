#!/usr/bin/env python3
"""
Claude CLI 高级集成管理器
自动检测、配置和维护Claude CLI与MCP服务的集成
"""

import json
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import tempfile
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClaudeCLIIntegrator:
    """Claude CLI集成管理器"""
    
    def __init__(self):
        self.os_type = platform.system().lower()
        self.config_dir = self._get_claude_config_dir()
        self.config_file = self.config_dir / "claude.json"
        self.backup_dir = self.config_dir / "backups"
        
        # 确保目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_claude_config_dir(self) -> Path:
        """获取Claude CLI配置目录"""
        if self.os_type == "windows":
            return Path(os.environ.get("APPDATA", "")) / "claude"
        else:
            return Path.home() / ".claude"
    
    def check_claude_cli_installation(self) -> Dict[str, Any]:
        """检查Claude CLI安装状态"""
        logger.info("检查Claude CLI安装状态...")
        
        result = {
            "installed": False,
            "version": None,
            "path": None,
            "installation_methods": []
        }
        
        # 检查直接命令
        try:
            cmd_result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if cmd_result.returncode == 0:
                result["installed"] = True
                result["version"] = cmd_result.stdout.strip()
                result["path"] = shutil.which("claude")
                logger.info(f"✓ Claude CLI已安装: {result['version']}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 检查npx方式
        if not result["installed"]:
            try:
                npx_result = subprocess.run(
                    ["npx", "claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if npx_result.returncode == 0:
                    result["installed"] = True
                    result["version"] = npx_result.stdout.strip()
                    result["path"] = "npx claude"
                    result["installation_methods"].append("npx")
                    logger.info(f"✓ Claude CLI通过npx可用: {result['version']}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        if not result["installed"]:
            logger.warning("Claude CLI未安装")
            result["installation_methods"] = self._get_installation_suggestions()
        
        return result
    
    def _get_installation_suggestions(self) -> List[str]:
        """获取安装建议"""
        suggestions = ["npm install -g @anthropic/claude-cli"]
        
        if self.os_type == "darwin":
            suggestions.append("brew install claude-cli")
        elif self.os_type == "linux":
            suggestions.extend([
                "下载二进制文件: https://github.com/anthropics/claude-cli/releases",
                "使用包管理器安装"
            ])
        elif self.os_type == "windows":
            suggestions.extend([
                "winget install Anthropic.ClaudeCLI",
                "下载Windows安装包"
            ])
        
        return suggestions
    
    def read_existing_config(self) -> Dict[str, Any]:
        """读取现有配置"""
        logger.info("读取现有Claude CLI配置...")
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info("✓ 现有配置已读取")
                return config
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"配置文件读取失败: {e}")
                return {}
        else:
            logger.info("未找到现有配置文件")
            return {}
    
    def backup_config(self) -> Optional[str]:
        """备份现有配置"""
        if not self.config_file.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"claude.json.backup.{timestamp}"
        
        try:
            shutil.copy2(self.config_file, backup_file)
            logger.info(f"✓ 配置已备份到: {backup_file}")
            return str(backup_file)
        except IOError as e:
            logger.error(f"配置备份失败: {e}")
            return None
    
    def detect_mcp_service_connection(self) -> Dict[str, Any]:
        """检测MCP服务连接方式"""
        logger.info("检测MCP服务连接方式...")
        
        connection_info = {
            "method": "unknown",
            "config": {},
            "available_methods": []
        }
        
        # 检查Docker容器
        if self._check_docker_container():
            connection_info["available_methods"].append("docker_exec")
            connection_info["method"] = "docker_exec"
            connection_info["config"] = {
                "command": "docker",
                "args": ["exec", "-i", "claude-memory-global", "python", "/app/global_mcp_server.py"],
                "env": {}
            }
        
        # 检查TCP端口
        if self._check_tcp_port(6334):
            connection_info["available_methods"].append("tcp")
            if connection_info["method"] == "unknown":
                connection_info["method"] = "tcp"
                connection_info["config"] = {
                    "command": "nc",
                    "args": ["localhost", "6334"],
                    "env": {}
                }
        
        # 检查本地进程
        if self._check_local_process():
            connection_info["available_methods"].append("stdio")
            if connection_info["method"] == "unknown":
                connection_info["method"] = "stdio"
                connection_info["config"] = {
                    "command": "python",
                    "args": [self._find_global_mcp_server_path()],
                    "env": {"PYTHONPATH": self._find_python_path()}
                }
        
        logger.info(f"✓ 检测到连接方式: {connection_info['method']}")
        return connection_info
    
    def _check_docker_container(self) -> bool:
        """检查Docker容器是否运行"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=claude-memory-global", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "claude-memory-global" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_tcp_port(self, port: int) -> bool:
        """检查TCP端口是否开放"""
        import socket
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except:
            return False
    
    def _check_local_process(self) -> bool:
        """检查本地进程"""
        try:
            # 检查进程
            if self.os_type == "windows":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe"],
                    capture_output=True,
                    text=True
                )
                return "global_mcp_server" in result.stdout
            else:
                result = subprocess.run(
                    ["pgrep", "-f", "global_mcp_server"],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
        except:
            return False
    
    def _find_global_mcp_server_path(self) -> str:
        """查找全局MCP服务器路径"""
        possible_paths = [
            Path.cwd() / "global_mcp_server.py",
            Path.cwd() / "src" / "global_mcp" / "global_mcp_server.py",
            Path(__file__).parent.parent / "src" / "global_mcp" / "global_mcp_server.py"
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return "/app/global_mcp_server.py"  # 默认Docker路径
    
    def _find_python_path(self) -> str:
        """查找Python路径"""
        possible_paths = [
            Path.cwd() / "src",
            Path(__file__).parent.parent / "src",
            "/app/src"
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return "/app/src"
    
    def generate_mcp_config(
        self, 
        connection_info: Dict[str, Any],
        service_name: str = "claude-memory-global"
    ) -> Dict[str, Any]:
        """生成MCP配置"""
        logger.info(f"生成MCP配置 (连接方式: {connection_info['method']})...")
        
        base_config = {
            "mcpServers": {
                service_name: connection_info["config"]
            }
        }
        
        # 添加服务描述
        base_config["mcpServers"][service_name]["description"] = (
            "Claude Memory 全局记忆管理服务 - 跨项目智能记忆共享"
        )
        
        # 根据连接方式添加特定配置
        if connection_info["method"] == "docker_exec":
            base_config["mcpServers"][service_name]["restart_policy"] = "on_failure"
            base_config["mcpServers"][service_name]["timeout"] = 30
        elif connection_info["method"] == "tcp":
            base_config["mcpServers"][service_name]["connection_timeout"] = 10
            base_config["mcpServers"][service_name]["retry_attempts"] = 3
        
        return base_config
    
    def merge_configurations(
        self, 
        existing_config: Dict[str, Any], 
        new_mcp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并配置"""
        logger.info("合并Claude CLI配置...")
        
        # 深度复制现有配置
        merged_config = existing_config.copy()
        
        # 确保mcpServers字段存在
        if "mcpServers" not in merged_config:
            merged_config["mcpServers"] = {}
        
        # 合并MCP服务器配置
        merged_config["mcpServers"].update(new_mcp_config["mcpServers"])
        
        # 添加元数据
        if "metadata" not in merged_config:
            merged_config["metadata"] = {}
        
        merged_config["metadata"].update({
            "claude_memory_integration": {
                "version": "2.0.0",
                "last_updated": datetime.now().isoformat(),
                "auto_configured": True
            }
        })
        
        logger.info("✓ 配置合并完成")
        return merged_config
    
    def write_config(self, config: Dict[str, Any]) -> bool:
        """写入配置文件"""
        logger.info("写入Claude CLI配置文件...")
        
        try:
            # 验证JSON格式
            json_str = json.dumps(config, indent=2, ensure_ascii=False)
            
            # 写入临时文件进行验证
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                temp_file.write(json_str)
                temp_path = temp_file.name
            
            # 验证临时文件
            try:
                with open(temp_path, 'r') as f:
                    json.load(f)
                logger.info("✓ 配置文件格式验证通过")
            except json.JSONDecodeError as e:
                logger.error(f"配置文件格式无效: {e}")
                os.unlink(temp_path)
                return False
            
            # 移动到目标位置
            shutil.move(temp_path, self.config_file)
            logger.info(f"✓ 配置文件已写入: {self.config_file}")
            return True
            
        except (IOError, OSError) as e:
            logger.error(f"配置文件写入失败: {e}")
            return False
    
    def test_mcp_connection(self, service_name: str = "claude-memory-global") -> Dict[str, Any]:
        """测试MCP连接"""
        logger.info("测试MCP服务器连接...")
        
        test_result = {
            "success": False,
            "service_found": False,
            "ping_success": False,
            "tools_available": False,
            "error": None
        }
        
        try:
            # 测试列出MCP服务器
            list_result = subprocess.run(
                ["claude", "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if list_result.returncode == 0:
                if service_name in list_result.stdout:
                    test_result["service_found"] = True
                    logger.info(f"✓ {service_name} 服务器已注册")
                    
                    # 测试ping
                    ping_result = subprocess.run(
                        ["claude", "mcp", "call", service_name, "ping"],
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    
                    if ping_result.returncode == 0:
                        test_result["ping_success"] = True
                        logger.info("✓ MCP服务器ping测试成功")
                        
                        # 测试工具列表
                        tools_result = subprocess.run(
                            ["claude", "mcp", "tools", service_name],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if tools_result.returncode == 0:
                            test_result["tools_available"] = True
                            logger.info("✓ MCP工具列表获取成功")
                            test_result["success"] = True
                        else:
                            test_result["error"] = f"工具列表获取失败: {tools_result.stderr}"
                    else:
                        test_result["error"] = f"Ping测试失败: {ping_result.stderr}"
                else:
                    test_result["error"] = f"{service_name} 未在MCP服务器列表中找到"
            else:
                test_result["error"] = f"无法获取MCP服务器列表: {list_result.stderr}"
                
        except subprocess.TimeoutExpired:
            test_result["error"] = "连接测试超时"
        except FileNotFoundError:
            test_result["error"] = "Claude CLI命令未找到"
        except Exception as e:
            test_result["error"] = f"测试过程中发生错误: {str(e)}"
        
        if test_result["success"]:
            logger.info("✓ MCP连接测试通过")
        else:
            logger.warning(f"⚠ MCP连接测试失败: {test_result['error']}")
        
        return test_result
    
    def setup_auto_integration(self) -> Dict[str, Any]:
        """设置自动集成"""
        logger.info("开始Claude CLI自动集成设置...")
        
        integration_result = {
            "success": False,
            "steps_completed": [],
            "warnings": [],
            "errors": []
        }
        
        try:
            # 1. 检查Claude CLI
            cli_status = self.check_claude_cli_installation()
            if not cli_status["installed"]:
                integration_result["errors"].append("Claude CLI未安装")
                return integration_result
            
            integration_result["steps_completed"].append("Claude CLI检查通过")
            
            # 2. 备份现有配置
            backup_path = self.backup_config()
            if backup_path:
                integration_result["steps_completed"].append(f"配置已备份: {backup_path}")
            
            # 3. 读取现有配置
            existing_config = self.read_existing_config()
            integration_result["steps_completed"].append("现有配置已读取")
            
            # 4. 检测MCP服务连接方式
            connection_info = self.detect_mcp_service_connection()
            if connection_info["method"] == "unknown":
                integration_result["warnings"].append("未检测到活跃的MCP服务")
            
            integration_result["steps_completed"].append(f"连接方式检测: {connection_info['method']}")
            
            # 5. 生成MCP配置
            mcp_config = self.generate_mcp_config(connection_info)
            integration_result["steps_completed"].append("MCP配置已生成")
            
            # 6. 合并配置
            final_config = self.merge_configurations(existing_config, mcp_config)
            integration_result["steps_completed"].append("配置已合并")
            
            # 7. 写入配置文件
            if self.write_config(final_config):
                integration_result["steps_completed"].append("配置文件已写入")
            else:
                integration_result["errors"].append("配置文件写入失败")
                return integration_result
            
            # 8. 测试连接
            test_result = self.test_mcp_connection()
            if test_result["success"]:
                integration_result["steps_completed"].append("MCP连接测试通过")
                integration_result["success"] = True
            else:
                integration_result["warnings"].append(f"MCP连接测试失败: {test_result['error']}")
                integration_result["success"] = True  # 配置成功，但连接测试失败
            
        except Exception as e:
            integration_result["errors"].append(f"集成过程中发生错误: {str(e)}")
            logger.error(f"自动集成失败: {e}", exc_info=True)
        
        return integration_result
    
    def generate_integration_report(self, integration_result: Dict[str, Any]) -> str:
        """生成集成报告"""
        report_lines = [
            "Claude CLI MCP 集成报告",
            "=" * 50,
            f"集成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"操作系统: {self.os_type}",
            f"配置目录: {self.config_dir}",
            "",
            f"集成结果: {'成功' if integration_result['success'] else '失败'}",
            ""
        ]
        
        if integration_result["steps_completed"]:
            report_lines.extend([
                "完成的步骤:",
                *[f"  ✓ {step}" for step in integration_result["steps_completed"]],
                ""
            ])
        
        if integration_result["warnings"]:
            report_lines.extend([
                "警告:",
                *[f"  ⚠ {warning}" for warning in integration_result["warnings"]],
                ""
            ])
        
        if integration_result["errors"]:
            report_lines.extend([
                "错误:",
                *[f"  ✗ {error}" for error in integration_result["errors"]],
                ""
            ])
        
        # 添加使用说明
        if integration_result["success"]:
            report_lines.extend([
                "使用说明:",
                "  1. 列出MCP服务器: claude mcp list",
                "  2. 搜索记忆: claude mcp call claude-memory-global memory_search '{\"query\": \"your search\"}'",
                "  3. 获取最近对话: claude mcp call claude-memory-global get_recent_conversations",
                "  4. 健康检查: claude mcp call claude-memory-global ping",
                ""
            ])
        
        return "\n".join(report_lines)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude CLI MCP 高级集成管理器")
    parser.add_argument("--check-only", action="store_true", help="仅检查状态，不进行配置")
    parser.add_argument("--test-connection", action="store_true", help="测试MCP连接")
    parser.add_argument("--service-name", default="claude-memory-global", help="MCP服务名称")
    parser.add_argument("--output-report", help="输出集成报告到文件")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    integrator = ClaudeCLIIntegrator()
    
    try:
        if args.check_only:
            # 仅检查状态
            cli_status = integrator.check_claude_cli_installation()
            connection_info = integrator.detect_mcp_service_connection()
            
            print("Claude CLI状态检查:")
            print(f"  安装状态: {'已安装' if cli_status['installed'] else '未安装'}")
            if cli_status['installed']:
                print(f"  版本: {cli_status['version']}")
                print(f"  路径: {cli_status['path']}")
            
            print(f"\nMCP服务连接检测:")
            print(f"  推荐连接方式: {connection_info['method']}")
            print(f"  可用连接方式: {', '.join(connection_info['available_methods'])}")
            
        elif args.test_connection:
            # 测试连接
            test_result = integrator.test_mcp_connection(args.service_name)
            print("MCP连接测试结果:")
            print(f"  整体成功: {test_result['success']}")
            print(f"  服务发现: {test_result['service_found']}")
            print(f"  Ping测试: {test_result['ping_success']}")
            print(f"  工具可用: {test_result['tools_available']}")
            if test_result['error']:
                print(f"  错误信息: {test_result['error']}")
        
        else:
            # 执行完整集成
            print("开始Claude CLI MCP自动集成...")
            integration_result = integrator.setup_auto_integration()
            
            # 生成报告
            report = integrator.generate_integration_report(integration_result)
            print(report)
            
            # 保存报告
            if args.output_report:
                with open(args.output_report, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n报告已保存到: {args.output_report}")
            
            # 退出码
            sys.exit(0 if integration_result["success"] else 1)
    
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"集成过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()