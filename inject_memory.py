#!/usr/bin/env python3
"""
Claude Memory 记忆注入脚本
直接调用API服务器进行记忆注入
"""

import sys
import json
import requests
import argparse
from typing import Optional

def inject_memory(original_prompt: str, query_text: Optional[str] = None) -> str:
    """
    调用Claude Memory API进行记忆注入
    
    Args:
        original_prompt: 原始用户输入
        query_text: 搜索查询文本，如果不提供则使用original_prompt
    
    Returns:
        增强后的prompt，如果失败则返回原始prompt
    """
    
    if not query_text:
        query_text = original_prompt
    
    # API服务器配置
    api_url = "http://localhost:8000/memory/inject"
    
    # 构建请求数据
    request_data = {
        "original_prompt": original_prompt,
        "query_text": query_text,
        "injection_mode": "comprehensive",
        "max_tokens": 999999,
        "project_id": "global"
    }
    
    try:
        # 发送请求
        response = requests.post(
            api_url,
            json=request_data,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # 检查响应格式
            if result.get("success") and "enhanced_prompt" in result:
                enhanced_prompt = result["enhanced_prompt"]
                
                # 如果增强后的prompt与原始prompt不同，说明注入了记忆
                if enhanced_prompt != original_prompt:
                    injected_memories = result.get("injected_memories", [])
                    print(f"✅ 已注入 {len(injected_memories)} 条相关历史记忆", file=sys.stderr)
                    return enhanced_prompt
                else:
                    print("ℹ️  未找到相关历史记忆", file=sys.stderr)
                    return original_prompt
            else:
                print(f"❌ API响应格式错误: {result}", file=sys.stderr)
                return original_prompt
        else:
            print(f"❌ API请求失败: {response.status_code} - {response.text}", file=sys.stderr)
            return original_prompt
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}", file=sys.stderr)
        return original_prompt
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}", file=sys.stderr)
        return original_prompt
    except Exception as e:
        print(f"❌ 未知错误: {e}", file=sys.stderr)
        return original_prompt

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Claude Memory 记忆注入工具")
    parser.add_argument("prompt", help="原始用户输入")
    parser.add_argument("--query", help="搜索查询文本（可选）")
    parser.add_argument("--silent", action="store_true", help="静默模式，不输出状态信息")
    
    args = parser.parse_args()
    
    # 如果是静默模式，重定向stderr
    if args.silent:
        sys.stderr = open('/dev/null', 'w')
    
    # 执行记忆注入
    enhanced_prompt = inject_memory(args.prompt, args.query)
    
    # 输出结果
    print(enhanced_prompt)

if __name__ == "__main__":
    main()