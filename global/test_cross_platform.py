#!/usr/bin/env python3
"""
跨平台兼容性测试套件
验证Claude Memory MCP服务在Linux、macOS、Windows等平台上的兼容性
"""

import asyncio
import os
import sys
import platform
import subprocess
import json
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PlatformInfo:
    """平台信息类"""
    
    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()
        self.processor = platform.processor()
        self.python_version = platform.python_version()
        self.platform_release = platform.release()
        self.platform_version = platform.version()
        
    def get_info(self) -> Dict[str, Any]:
        """获取平台信息"""
        return {
            "system": self.system,
            "machine": self.machine,
            "processor": self.processor,
            "python_version": self.python_version,
            "platform_release": self.platform_release,
            "platform_version": self.platform_version,
            "architecture": self._get_architecture(),
            "is_64bit": sys.maxsize > 2**32,
            "endianness": sys.byteorder,
            "path_separator": os.pathsep,
            "line_separator": repr(os.linesep),
            "default_encoding": sys.getdefaultencoding(),
            "filesystem_encoding": sys.getfilesystemencoding()
        }
    
    def _get_architecture(self) -> str:
        """获取架构信息"""
        if self.machine.lower() in ['amd64', 'x86_64']:
            return 'x64'
        elif self.machine.lower() in ['i386', 'i686', 'x86']:
            return 'x86'
        elif self.machine.lower() in ['arm64', 'aarch64']:
            return 'arm64'
        elif self.machine.lower().startswith('arm'):
            return 'arm'
        else:
            return self.machine


class CrossPlatformTester:
    """跨平台测试器"""
    
    def __init__(self):
        self.platform_info = PlatformInfo()
        self.test_results = {}
        self.temp_dir = None
        self.project_root = Path(__file__).parent
        
    def setup_test_environment(self):
        """设置测试环境"""
        logger.info("设置跨平台测试环境...")
        
        # 创建临时测试目录
        self.temp_dir = tempfile.mkdtemp(prefix="claude_memory_test_")
        logger.info(f"临时测试目录: {self.temp_dir}")
        
        # 复制必要的文件到测试目录
        test_files = [
            "src",
            "config",
            "requirements.global.txt",
            "docker-compose.global.yml",
            "Dockerfile.global"
        ]
        
        for file_name in test_files:
            src_path = self.project_root / file_name
            if src_path.exists():
                dst_path = Path(self.temp_dir) / file_name
                if src_path.is_dir():
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
                logger.info(f"复制测试文件: {file_name}")
        
        return self.temp_dir
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时目录: {self.temp_dir}")
    
    def test_python_environment(self) -> Dict[str, Any]:
        """测试Python环境兼容性"""
        logger.info("测试Python环境兼容性...")
        
        result = {
            "status": "success",
            "platform_info": self.platform_info.get_info(),
            "python_checks": {},
            "errors": []
        }
        
        try:
            # 检查Python版本
            python_version_tuple = tuple(map(int, platform.python_version().split('.')))
            if python_version_tuple >= (3, 8):
                result["python_checks"]["version"] = {"status": "ok", "version": platform.python_version()}
            else:
                result["python_checks"]["version"] = {"status": "error", "version": platform.python_version()}
                result["errors"].append(f"Python版本过低: {platform.python_version()}, 需要 >= 3.8")
            
            # 检查必需模块
            required_modules = [
                "asyncio", "sqlite3", "json", "pathlib", "logging",
                "datetime", "uuid", "hashlib", "typing"
            ]
            
            module_results = {}
            for module in required_modules:
                try:
                    __import__(module)
                    module_results[module] = {"status": "ok"}
                except ImportError as e:
                    module_results[module] = {"status": "error", "error": str(e)}
                    result["errors"].append(f"缺少模块: {module}")
            
            result["python_checks"]["modules"] = module_results
            
            # 检查可选模块
            optional_modules = {
                "aiosqlite": "异步SQLite支持",
                "yaml": "YAML配置文件支持",
                "psutil": "系统性能监控"
            }
            
            optional_results = {}
            for module, description in optional_modules.items():
                try:
                    __import__(module)
                    optional_results[module] = {"status": "ok", "description": description}
                except ImportError:
                    optional_results[module] = {"status": "missing", "description": description}
            
            result["python_checks"]["optional_modules"] = optional_results
            
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Python环境测试异常: {str(e)}")
        
        return result
    
    def test_file_system_compatibility(self) -> Dict[str, Any]:
        """测试文件系统兼容性"""
        logger.info("测试文件系统兼容性...")
        
        result = {
            "status": "success",
            "filesystem_checks": {},
            "errors": []
        }
        
        try:
            test_dir = Path(self.temp_dir) / "fs_test"
            test_dir.mkdir(exist_ok=True)
            
            # 测试路径分隔符
            path_sep = os.sep
            result["filesystem_checks"]["path_separator"] = path_sep
            
            # 测试长文件名支持
            long_filename = "a" * 200 + ".txt"
            long_file_path = test_dir / long_filename
            try:
                long_file_path.write_text("test")
                long_file_path.unlink()
                result["filesystem_checks"]["long_filename"] = {"status": "ok"}
            except OSError as e:
                result["filesystem_checks"]["long_filename"] = {"status": "error", "error": str(e)}
            
            # 测试Unicode文件名
            unicode_filename = "测试文件_émojì_🧠.txt"
            unicode_file_path = test_dir / unicode_filename
            try:
                unicode_file_path.write_text("Unicode test", encoding='utf-8')
                content = unicode_file_path.read_text(encoding='utf-8')
                unicode_file_path.unlink()
                result["filesystem_checks"]["unicode_filename"] = {"status": "ok"}
            except (OSError, UnicodeError) as e:
                result["filesystem_checks"]["unicode_filename"] = {"status": "error", "error": str(e)}
            
            # 测试文件权限
            perm_file = test_dir / "permission_test.txt"
            try:
                perm_file.write_text("permission test")
                
                # 测试读权限
                content = perm_file.read_text()
                
                # 测试写权限
                perm_file.write_text("permission test updated")
                
                # 清理
                perm_file.unlink()
                result["filesystem_checks"]["permissions"] = {"status": "ok"}
            except (OSError, PermissionError) as e:
                result["filesystem_checks"]["permissions"] = {"status": "error", "error": str(e)}
            
            # 测试目录创建和删除
            nested_dir = test_dir / "nested" / "deep" / "directory"
            try:
                nested_dir.mkdir(parents=True, exist_ok=True)
                nested_dir.rmdir()
                (test_dir / "nested" / "deep").rmdir()
                (test_dir / "nested").rmdir()
                result["filesystem_checks"]["nested_directories"] = {"status": "ok"}
            except OSError as e:
                result["filesystem_checks"]["nested_directories"] = {"status": "error", "error": str(e)}
            
            # 测试临时文件支持
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                    temp_path = f.name
                    f.write("temp test")
                
                # 读取临时文件
                with open(temp_path, 'r') as f:
                    content = f.read()
                
                # 删除临时文件
                os.unlink(temp_path)
                result["filesystem_checks"]["temp_files"] = {"status": "ok"}
            except OSError as e:
                result["filesystem_checks"]["temp_files"] = {"status": "error", "error": str(e)}
                
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"文件系统测试异常: {str(e)}")
        
        return result
    
    def test_database_compatibility(self) -> Dict[str, Any]:
        """测试数据库兼容性"""
        logger.info("测试数据库兼容性...")
        
        result = {
            "status": "success",
            "database_checks": {},
            "errors": []
        }
        
        try:
            import sqlite3
            
            # 测试SQLite基本功能
            db_path = Path(self.temp_dir) / "test.db"
            
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # 创建测试表
                cursor.execute("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 插入测试数据
                cursor.execute("INSERT INTO test_table (name, data) VALUES (?, ?)", 
                             ("test", "test data"))
                
                # 查询测试数据
                cursor.execute("SELECT * FROM test_table")
                rows = cursor.fetchall()
                
                conn.commit()
                conn.close()
                
                if len(rows) == 1:
                    result["database_checks"]["sqlite_basic"] = {"status": "ok"}
                else:
                    result["database_checks"]["sqlite_basic"] = {"status": "error", "error": "数据查询异常"}
                
            except sqlite3.Error as e:
                result["database_checks"]["sqlite_basic"] = {"status": "error", "error": str(e)}
            
            # 测试WAL模式（并发优化）
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                cursor.execute("PRAGMA journal_mode=WAL")
                mode = cursor.fetchone()[0]
                
                conn.close()
                
                if mode.upper() == "WAL":
                    result["database_checks"]["wal_mode"] = {"status": "ok"}
                else:
                    result["database_checks"]["wal_mode"] = {"status": "warning", "mode": mode}
                
            except sqlite3.Error as e:
                result["database_checks"]["wal_mode"] = {"status": "error", "error": str(e)}
            
            # 测试Unicode支持
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                unicode_text = "测试Unicode: émojì 🧠 データベース"
                cursor.execute("INSERT INTO test_table (name, data) VALUES (?, ?)",
                             ("unicode_test", unicode_text))
                
                cursor.execute("SELECT data FROM test_table WHERE name = ?", ("unicode_test",))
                retrieved_text = cursor.fetchone()[0]
                
                conn.commit()
                conn.close()
                
                if retrieved_text == unicode_text:
                    result["database_checks"]["unicode_support"] = {"status": "ok"}
                else:
                    result["database_checks"]["unicode_support"] = {"status": "error", "error": "Unicode数据不匹配"}
                
            except (sqlite3.Error, UnicodeError) as e:
                result["database_checks"]["unicode_support"] = {"status": "error", "error": str(e)}
            
            # 清理测试数据库
            if db_path.exists():
                db_path.unlink()
                
        except ImportError:
            result["status"] = "error"
            result["errors"].append("SQLite模块不可用")
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"数据库测试异常: {str(e)}")
        
        return result
    
    def test_networking_compatibility(self) -> Dict[str, Any]:
        """测试网络兼容性"""
        logger.info("测试网络兼容性...")
        
        result = {
            "status": "success",
            "network_checks": {},
            "errors": []
        }
        
        try:
            import socket
            
            # 测试IPv4支持
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('localhost', 0))
                port = sock.getsockname()[1]
                sock.close()
                result["network_checks"]["ipv4"] = {"status": "ok", "test_port": port}
            except OSError as e:
                result["network_checks"]["ipv4"] = {"status": "error", "error": str(e)}
            
            # 测试IPv6支持
            try:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                sock.bind(('::1', 0))
                port = sock.getsockname()[1]
                sock.close()
                result["network_checks"]["ipv6"] = {"status": "ok", "test_port": port}
            except OSError as e:
                result["network_checks"]["ipv6"] = {"status": "warning", "error": str(e)}
            
            # 测试端口绑定
            test_ports = [6334, 6335, 8080, 0]  # 0表示系统分配
            port_results = {}
            
            for port in test_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(('localhost', port))
                    actual_port = sock.getsockname()[1]
                    sock.close()
                    port_results[str(port)] = {"status": "ok", "actual_port": actual_port}
                except OSError as e:
                    port_results[str(port)] = {"status": "error", "error": str(e)}
            
            result["network_checks"]["port_binding"] = port_results
            
            # 测试主机名解析
            try:
                localhost_ip = socket.gethostbyname('localhost')
                result["network_checks"]["hostname_resolution"] = {
                    "status": "ok", 
                    "localhost_ip": localhost_ip
                }
            except socket.gaierror as e:
                result["network_checks"]["hostname_resolution"] = {"status": "error", "error": str(e)}
                
        except ImportError:
            result["status"] = "error"
            result["errors"].append("Socket模块不可用")
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"网络测试异常: {str(e)}")
        
        return result
    
    def test_docker_compatibility(self) -> Dict[str, Any]:
        """测试Docker兼容性"""
        logger.info("测试Docker兼容性...")
        
        result = {
            "status": "success",
            "docker_checks": {},
            "errors": []
        }
        
        try:
            # 检查Docker命令是否可用
            docker_version = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if docker_version.returncode == 0:
                result["docker_checks"]["docker_installed"] = {
                    "status": "ok",
                    "version": docker_version.stdout.strip()
                }
                
                # 检查Docker是否运行
                docker_info = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if docker_info.returncode == 0:
                    result["docker_checks"]["docker_running"] = {"status": "ok"}
                    
                    # 检查Docker Compose
                    try:
                        compose_version = subprocess.run(
                            ["docker", "compose", "version"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if compose_version.returncode == 0:
                            result["docker_checks"]["docker_compose"] = {
                                "status": "ok",
                                "version": compose_version.stdout.strip()
                            }
                        else:
                            # 尝试旧版本的docker-compose
                            compose_version = subprocess.run(
                                ["docker-compose", "--version"],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            
                            if compose_version.returncode == 0:
                                result["docker_checks"]["docker_compose"] = {
                                    "status": "ok",
                                    "version": compose_version.stdout.strip(),
                                    "type": "legacy"
                                }
                            else:
                                result["docker_checks"]["docker_compose"] = {
                                    "status": "error",
                                    "error": "Docker Compose不可用"
                                }
                    except FileNotFoundError:
                        result["docker_checks"]["docker_compose"] = {
                            "status": "error",
                            "error": "Docker Compose命令未找到"
                        }
                else:
                    result["docker_checks"]["docker_running"] = {
                        "status": "error",
                        "error": "Docker守护进程未运行"
                    }
            else:
                result["docker_checks"]["docker_installed"] = {
                    "status": "error",
                    "error": "Docker未安装或不可访问"
                }
                
        except FileNotFoundError:
            result["docker_checks"]["docker_installed"] = {
                "status": "error",
                "error": "Docker命令未找到"
            }
        except subprocess.TimeoutExpired:
            result["docker_checks"]["docker_installed"] = {
                "status": "error",
                "error": "Docker命令执行超时"
            }
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Docker测试异常: {str(e)}")
        
        return result
    
    def test_claude_cli_compatibility(self) -> Dict[str, Any]:
        """测试Claude CLI兼容性"""
        logger.info("测试Claude CLI兼容性...")
        
        result = {
            "status": "success",
            "claude_cli_checks": {},
            "errors": []
        }
        
        try:
            # 检查Claude CLI是否安装
            claude_version = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if claude_version.returncode == 0:
                result["claude_cli_checks"]["claude_installed"] = {
                    "status": "ok",
                    "version": claude_version.stdout.strip()
                }
                
                # 检查MCP支持
                mcp_help = subprocess.run(
                    ["claude", "mcp", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if mcp_help.returncode == 0:
                    result["claude_cli_checks"]["mcp_support"] = {"status": "ok"}
                else:
                    result["claude_cli_checks"]["mcp_support"] = {
                        "status": "error",
                        "error": "MCP子命令不可用"
                    }
            else:
                result["claude_cli_checks"]["claude_installed"] = {
                    "status": "warning",
                    "error": "Claude CLI未安装（可选组件）"
                }
                
        except FileNotFoundError:
            result["claude_cli_checks"]["claude_installed"] = {
                "status": "warning",
                "error": "Claude CLI命令未找到（可选组件）"
            }
        except subprocess.TimeoutExpired:
            result["claude_cli_checks"]["claude_installed"] = {
                "status": "error",
                "error": "Claude CLI命令执行超时"
            }
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"Claude CLI测试异常: {str(e)}")
        
        return result
    
    def test_memory_service_functionality(self) -> Dict[str, Any]:
        """测试记忆服务功能"""
        logger.info("测试记忆服务核心功能...")
        
        result = {
            "status": "success",
            "service_checks": {},
            "errors": []
        }
        
        try:
            # 添加src路径以便导入模块
            sys.path.insert(0, str(Path(self.temp_dir) / "src"))
            
            try:
                from global_mcp.global_memory_manager import GlobalMemoryManager
                result["service_checks"]["module_import"] = {"status": "ok"}
            except ImportError as e:
                result["service_checks"]["module_import"] = {"status": "error", "error": str(e)}
                return result
            
            # 测试配置加载
            test_config = {
                "database": {
                    "url": f"sqlite:///{self.temp_dir}/test_memory.db"
                },
                "vector_store": {
                    "url": "http://localhost:6333",
                    "collection_name": "test_memories"
                },
                "memory": {
                    "cross_project_sharing": True,
                    "project_isolation": False,
                    "retention_days": 365
                }
            }
            
            try:
                manager = GlobalMemoryManager(test_config)
                result["service_checks"]["manager_initialization"] = {"status": "ok"}
            except Exception as e:
                result["service_checks"]["manager_initialization"] = {"status": "error", "error": str(e)}
                return result
            
            # 测试异步功能
            async def test_async_functionality():
                try:
                    # 测试健康检查
                    health_result = await manager.health_check()
                    if "timestamp" in health_result:
                        return {"status": "ok", "health_check": "passed"}
                    else:
                        return {"status": "error", "error": "健康检查返回格式异常"}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            
            # 运行异步测试
            import asyncio
            async_result = asyncio.run(test_async_functionality())
            result["service_checks"]["async_functionality"] = async_result
            
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"服务功能测试异常: {str(e)}")
        finally:
            # 清理sys.path
            if str(Path(self.temp_dir) / "src") in sys.path:
                sys.path.remove(str(Path(self.temp_dir) / "src"))
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有跨平台测试"""
        logger.info("开始跨平台兼容性测试...")
        
        test_start_time = time.time()
        
        try:
            # 设置测试环境
            self.setup_test_environment()
            
            # 执行各项测试
            test_suite = {
                "python_environment": self.test_python_environment,
                "filesystem": self.test_file_system_compatibility,
                "database": self.test_database_compatibility,
                "networking": self.test_networking_compatibility,
                "docker": self.test_docker_compatibility,
                "claude_cli": self.test_claude_cli_compatibility,
                "memory_service": self.test_memory_service_functionality
            }
            
            results = {}
            for test_name, test_func in test_suite.items():
                logger.info(f"执行测试: {test_name}")
                try:
                    results[test_name] = test_func()
                except Exception as e:
                    results[test_name] = {
                        "status": "error",
                        "errors": [f"测试执行异常: {str(e)}"]
                    }
            
            # 生成总体结果
            test_end_time = time.time()
            
            total_result = {
                "test_timestamp": datetime.now().isoformat(),
                "test_duration": test_end_time - test_start_time,
                "platform_info": self.platform_info.get_info(),
                "test_results": results,
                "overall_status": self._calculate_overall_status(results),
                "compatibility_summary": self._generate_compatibility_summary(results)
            }
            
            return total_result
            
        finally:
            # 清理测试环境
            self.cleanup_test_environment()
    
    def _calculate_overall_status(self, results: Dict[str, Any]) -> str:
        """计算总体状态"""
        error_count = 0
        warning_count = 0
        success_count = 0
        
        for test_result in results.values():
            if test_result["status"] == "error":
                error_count += 1
            elif test_result["status"] == "warning":
                warning_count += 1
            else:
                success_count += 1
        
        if error_count > 0:
            return "failed"
        elif warning_count > 0:
            return "warning"
        else:
            return "success"
    
    def _generate_compatibility_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成兼容性总结"""
        summary = {
            "compatible": True,
            "issues": [],
            "recommendations": []
        }
        
        # 检查关键组件
        if results.get("python_environment", {}).get("status") == "error":
            summary["compatible"] = False
            summary["issues"].append("Python环境不兼容")
            summary["recommendations"].append("升级Python到3.8+版本")
        
        if results.get("database", {}).get("status") == "error":
            summary["compatible"] = False
            summary["issues"].append("数据库功能不可用")
            summary["recommendations"].append("检查SQLite安装和权限")
        
        if results.get("filesystem", {}).get("status") == "error":
            summary["compatible"] = False
            summary["issues"].append("文件系统操作异常")
            summary["recommendations"].append("检查文件系统权限和编码")
        
        # 检查可选组件
        if results.get("docker", {}).get("status") == "error":
            summary["issues"].append("Docker不可用（影响容器化部署）")
            summary["recommendations"].append("安装Docker以支持容器化部署")
        
        if results.get("claude_cli", {}).get("status") == "error":
            summary["issues"].append("Claude CLI不可用（影响MCP集成）")
            summary["recommendations"].append("安装Claude CLI以支持MCP功能")
        
        return summary


def main():
    """主函数"""
    tester = CrossPlatformTester()
    
    try:
        logger.info("🧪 开始Claude Memory MCP跨平台兼容性测试")
        
        # 运行所有测试
        results = tester.run_all_tests()
        
        # 保存测试报告
        report_file = Path(__file__).parent / "test_results" / f"cross_platform_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ 测试报告已保存: {report_file}")
        
        # 显示测试结果
        print("\n" + "="*80)
        print("🧪 Claude Memory MCP 跨平台兼容性测试报告")
        print("="*80)
        
        platform_info = results["platform_info"]
        print(f"\n🖥️  测试平台信息:")
        print(f"  操作系统: {platform_info['system']} {platform_info['platform_release']}")
        print(f"  架构: {platform_info['architecture']}")
        print(f"  Python版本: {platform_info['python_version']}")
        print(f"  处理器: {platform_info['processor']}")
        
        print(f"\n⏱️  测试时长: {results['test_duration']:.2f}秒")
        print(f"🎯 总体状态: {results['overall_status'].upper()}")
        
        # 显示各项测试结果
        print(f"\n📊 测试结果详情:")
        for test_name, test_result in results["test_results"].items():
            status_icon = "✅" if test_result["status"] == "success" else "⚠️" if test_result["status"] == "warning" else "❌"
            print(f"  {status_icon} {test_name}: {test_result['status']}")
            
            if test_result.get("errors"):
                for error in test_result["errors"]:
                    print(f"      ❌ {error}")
        
        # 显示兼容性总结
        compatibility = results["compatibility_summary"]
        print(f"\n🎯 兼容性评估:")
        print(f"  总体兼容性: {'✅ 兼容' if compatibility['compatible'] else '❌ 不兼容'}")
        
        if compatibility["issues"]:
            print(f"  发现问题:")
            for issue in compatibility["issues"]:
                print(f"    ⚠️ {issue}")
        
        if compatibility["recommendations"]:
            print(f"  建议:")
            for rec in compatibility["recommendations"]:
                print(f"    💡 {rec}")
        
        # 返回适当的退出码
        if results["overall_status"] == "failed":
            sys.exit(1)
        elif results["overall_status"] == "warning":
            print(f"\n⚠️  测试完成，但存在警告。系统基本可用。")
        else:
            print(f"\n🎉 所有测试通过！系统在当前平台完全兼容。")
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()