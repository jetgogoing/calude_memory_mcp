#!/usr/bin/env python3
"""
探索Claude CLI对话捕获的替代技术方案
"""
import os
import sys
import subprocess
import json
import time
from pathlib import Path
import shutil


class ClaudeAlternativesExplorer:
    def __init__(self):
        self.claude_path = shutil.which('claude')
        self.home_dir = Path.home()
        
    def explore_claude_config(self):
        """探索Claude CLI的配置文件和环境变量"""
        print("\n=== 1. Claude CLI Hook方案探索 ===")
        
        # 检查可能的配置文件位置
        config_locations = [
            self.home_dir / '.claude' / 'config.json',
            self.home_dir / '.claude' / 'config.yaml',
            self.home_dir / '.claude' / 'config.toml',
            self.home_dir / '.config' / 'claude' / 'config.json',
            self.home_dir / '.clauderc',
            Path('/etc/claude/config.json'),
        ]
        
        print("\n检查配置文件:")
        for config_path in config_locations:
            if config_path.exists():
                print(f"  ✓ 找到: {config_path}")
                try:
                    with open(config_path, 'r') as f:
                        content = f.read()
                        print(f"    内容预览: {content[:200]}...")
                except Exception as e:
                    print(f"    读取失败: {e}")
            else:
                print(f"  ✗ 不存在: {config_path}")
        
        # 检查环境变量
        print("\n检查Claude相关环境变量:")
        claude_env_vars = [
            var for var in os.environ 
            if 'CLAUDE' in var.upper() or 'ANTHROPIC' in var.upper()
        ]
        
        if claude_env_vars:
            for var in claude_env_vars:
                print(f"  {var} = {os.environ[var]}")
        else:
            print("  未找到Claude相关环境变量")
            
        # 尝试获取claude版本和帮助信息
        print("\n检查Claude CLI支持的选项:")
        try:
            result = subprocess.run(
                ['claude', '--help'],
                capture_output=True,
                text=True
            )
            help_text = result.stdout
            
            # 查找可能的hook或plugin相关选项
            hook_keywords = ['hook', 'plugin', 'extension', 'middleware', 'intercept', 'log', 'debug']
            found_keywords = []
            
            for keyword in hook_keywords:
                if keyword.lower() in help_text.lower():
                    found_keywords.append(keyword)
                    
            if found_keywords:
                print(f"  发现相关关键词: {found_keywords}")
            else:
                print("  未发现hook/plugin相关选项")
                
        except Exception as e:
            print(f"  获取帮助信息失败: {e}")
            
    def explore_path_intercept(self):
        """探索PATH拦截方案"""
        print("\n=== 2. 系统级命令拦截方案探索 ===")
        
        print(f"\n当前claude路径: {self.claude_path}")
        print(f"当前PATH优先级:")
        
        paths = os.environ.get('PATH', '').split(':')
        for i, path in enumerate(paths[:10]):  # 只显示前10个
            print(f"  {i+1}. {path}")
            
        # 建议的拦截器路径
        intercept_dir = self.home_dir / '.local' / 'bin'
        print(f"\n建议的拦截器目录: {intercept_dir}")
        print(f"该目录是否存在: {intercept_dir.exists()}")
        print(f"该目录是否在PATH中: {str(intercept_dir) in os.environ.get('PATH', '')}")
        
        # 检查是否已有其他工具使用类似方案
        if intercept_dir.exists():
            existing_wrappers = list(intercept_dir.glob('*'))
            if existing_wrappers:
                print(f"\n发现已存在的包装器:")
                for wrapper in existing_wrappers[:5]:
                    print(f"  - {wrapper.name}")
                    
    def explore_log_monitoring(self):
        """探索日志监控方案"""
        print("\n=== 3. 日志监控方案探索 ===")
        
        # 检查可能的日志位置
        log_locations = [
            self.home_dir / '.claude' / 'logs',
            self.home_dir / '.cache' / 'claude',
            self.home_dir / '.local' / 'share' / 'claude',
            Path('/var/log/claude'),
            Path('/tmp') / f'claude-{os.getuid()}',
        ]
        
        print("\n检查日志目录:")
        for log_dir in log_locations:
            if log_dir.exists():
                print(f"  ✓ 找到: {log_dir}")
                # 列出最近的日志文件
                try:
                    log_files = list(log_dir.glob('*'))
                    if log_files:
                        recent_files = sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]
                        print(f"    最近的文件:")
                        for f in recent_files:
                            print(f"      - {f.name} (大小: {f.stat().st_size} bytes)")
                except Exception as e:
                    print(f"    读取失败: {e}")
            else:
                print(f"  ✗ 不存在: {log_dir}")
                
        # 检查claude进程是否创建临时文件
        print("\n检查claude运行时的文件操作:")
        print("  提示: 可以使用 strace -e trace=file claude <命令> 来监控文件操作")
        
    def explore_api_proxy(self):
        """探索API代理方案"""
        print("\n=== 4. API代理方案探索 ===")
        
        # 检查代理相关环境变量
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
        
        print("\n检查代理环境变量:")
        for var in proxy_vars:
            value = os.environ.get(var)
            if value:
                print(f"  {var} = {value}")
            else:
                print(f"  {var} = (未设置)")
                
        # 检查Claude是否支持代理设置
        print("\n检查Claude API端点:")
        api_endpoints = [
            'https://api.anthropic.com',
            'https://claude.ai',
        ]
        
        print("  可能的API端点:")
        for endpoint in api_endpoints:
            print(f"    - {endpoint}")
            
        print("\n提示: 可以使用以下方法监控网络请求:")
        print("  1. tcpdump -i any -w claude.pcap host api.anthropic.com")
        print("  2. 使用mitmproxy作为HTTPS代理")
        print("  3. 设置自定义CA证书进行SSL拦截")
        
    def analyze_feasibility(self):
        """分析各方案的可行性"""
        print("\n=== 方案可行性分析 ===")
        
        analysis = {
            "Claude CLI Hook方案": {
                "实现复杂度": "低",
                "可靠性": "高",
                "用户体验影响": "无",
                "跨平台兼容性": "优秀",
                "可行性": "取决于Claude CLI是否支持",
                "优点": ["官方支持", "最稳定", "无需额外维护"],
                "缺点": ["需要Claude CLI内置支持", "可能不存在此功能"]
            },
            "PATH拦截方案": {
                "实现复杂度": "中",
                "可靠性": "高",
                "用户体验影响": "极小",
                "跨平台兼容性": "良好",
                "可行性": "高",
                "优点": ["透明拦截", "用户无感知", "完全控制"],
                "缺点": ["需要维护包装脚本", "PATH配置要求", "可能与系统更新冲突"]
            },
            "日志监控方案": {
                "实现复杂度": "中",
                "可靠性": "中",
                "用户体验影响": "无",
                "跨平台兼容性": "中等",
                "可行性": "取决于日志输出",
                "优点": ["非侵入式", "可以后台运行"],
                "缺点": ["依赖日志格式", "可能延迟", "日志可能不完整"]
            },
            "API代理方案": {
                "实现复杂度": "高",
                "可靠性": "中",
                "用户体验影响": "可能有延迟",
                "跨平台兼容性": "中等",
                "可行性": "中",
                "优点": ["完整捕获API通信", "可以修改请求/响应"],
                "缺点": ["SSL证书问题", "性能开销", "配置复杂", "可能违反服务条款"]
            }
        }
        
        for method, details in analysis.items():
            print(f"\n{method}:")
            for key, value in details.items():
                if isinstance(value, list):
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
                    
    def recommend_solution(self):
        """推荐最佳解决方案"""
        print("\n=== 推荐方案 ===")
        print("\n基于分析，推荐采用组合方案:")
        print("\n1. 主方案: PATH拦截")
        print("   - 创建claude包装脚本放在~/.local/bin/")
        print("   - 确保~/.local/bin在PATH中优先级高于系统claude")
        print("   - 包装脚本负责记录输入输出并调用真实claude")
        print("\n2. 备选方案: 进程监控")
        print("   - 使用脚本监控claude进程")
        print("   - 通过/proc/<pid>/fd/读取标准输入输出")
        print("   - 适用于PATH方案失效的情况")
        print("\n3. 实现建议:")
        print("   - 使用Python编写包装器，确保跨平台兼容")
        print("   - 异步记录对话，避免影响响应速度")
        print("   - 提供开关机制，用户可以禁用记录")
        print("   - 记录元数据：时间戳、命令参数、环境变量等")


def main():
    explorer = ClaudeAlternativesExplorer()
    
    # 执行所有探索
    explorer.explore_claude_config()
    explorer.explore_path_intercept()
    explorer.explore_log_monitoring()
    explorer.explore_api_proxy()
    explorer.analyze_feasibility()
    explorer.recommend_solution()
    

if __name__ == "__main__":
    main()