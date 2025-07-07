#!/usr/bin/env python3
"""
API密钥配置向导
帮助用户安全地配置所需的API密钥
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

def main():
    """主配置流程"""
    print("🔧 Claude Memory MCP服务 - API密钥配置向导")
    print("=" * 60)
    
    # 配置文件路径
    config_dir = Path(__file__).parent.parent / "config"
    env_file = config_dir / ".env"
    env_example = config_dir / ".env.example"
    
    # 检查示例文件是否存在
    if not env_example.exists():
        print(f"❌ 未找到配置模板文件: {env_example}")
        sys.exit(1)
    
    print(f"📁 配置目录: {config_dir}")
    print(f"📝 配置文件: {env_file}")
    
    # 如果.env文件已存在，询问是否覆盖
    if env_file.exists():
        response = input("\n⚠️  配置文件已存在，是否覆盖? (y/N): ").strip().lower()
        if response != 'y':
            print("🚫 配置已取消")
            sys.exit(0)
    
    # 读取模板文件
    with open(env_example, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    print("\n🔑 开始配置API密钥...")
    print("💡 提示: 可以跳过某些API密钥，稍后手动配置")
    print("-" * 60)
    
    # API密钥配置项
    api_keys = {
        'OPENAI_API_KEY': {
            'name': 'OpenAI API密钥',
            'description': 'GPT模型访问密钥',
            'required': False,
            'example': 'sk-...',
            'url': 'https://platform.openai.com/api-keys'
        },
        'ANTHROPIC_API_KEY': {
            'name': 'Anthropic Claude API密钥', 
            'description': 'Claude模型访问密钥',
            'required': False,
            'example': 'sk-ant-...',
            'url': 'https://console.anthropic.com/'
        },
        'GOOGLE_API_KEY': {
            'name': 'Google Gemini API密钥',
            'description': 'Gemini模型访问密钥',
            'required': False,
            'example': 'AIza...',
            'url': 'https://makersuite.google.com/app/apikey'
        },
        'OPENROUTER_API_KEY': {
            'name': 'OpenRouter API密钥',
            'description': '多模型统一访问密钥',
            'required': False,
            'example': 'sk-or-...',
            'url': 'https://openrouter.ai/keys'
        },
        'SILICONFLOW_API_KEY': {
            'name': 'SiliconFlow API密钥',
            'description': '国内模型访问密钥',
            'required': False,
            'example': 'sk-...',
            'url': 'https://siliconflow.cn/'
        }
    }
    
    # 收集用户输入
    user_values = {}
    
    for key, info in api_keys.items():
        print(f"\n📌 {info['name']}")
        print(f"   用途: {info['description']}")
        print(f"   获取地址: {info['url']}")
        print(f"   示例格式: {info['example']}")
        
        while True:
            value = input(f"   请输入 {key} (回车跳过): ").strip()
            
            if not value:
                print(f"   ⏭️  跳过 {info['name']}")
                break
            
            # 基本格式验证
            if validate_api_key(key, value):
                user_values[key] = value
                print(f"   ✅ {info['name']} 已设置")
                break
            else:
                print(f"   ❌ API密钥格式似乎不正确，请重新输入")
    
    # 其他重要配置
    print("\n🔧 其他配置项...")
    
    # 数据库配置
    print(f"\n📊 数据库配置")
    db_choice = input("   选择数据库 (1: SQLite[默认], 2: PostgreSQL): ").strip()
    
    if db_choice == "2":
        db_host = input("   PostgreSQL主机 (localhost): ").strip() or "localhost"
        db_port = input("   PostgreSQL端口 (5432): ").strip() or "5432"
        db_name = input("   数据库名称 (claude_memory): ").strip() or "claude_memory"
        db_user = input("   用户名: ").strip()
        db_pass = input("   密码: ").strip()
        
        if db_user and db_pass:
            user_values['DATABASE_URL'] = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    # Qdrant配置
    print(f"\n🔍 向量数据库配置 (Qdrant)")
    qdrant_url = input("   Qdrant服务地址 (http://localhost:6333): ").strip()
    if qdrant_url:
        user_values['QDRANT_URL'] = qdrant_url
    
    qdrant_key = input("   Qdrant API密钥 (可选): ").strip()
    if qdrant_key:
        user_values['QDRANT_API_KEY'] = qdrant_key
    
    # 服务密钥
    print(f"\n🔐 安全配置")
    service_key = input("   服务密钥 (自动生成): ").strip()
    if not service_key:
        import secrets
        service_key = secrets.token_urlsafe(32)
        print(f"   🎲 已生成随机密钥: {service_key[:16]}...")
    user_values['SERVICE_SECRET_KEY'] = service_key
    
    # 生成最终配置文件
    final_content = template_content
    
    for key, value in user_values.items():
        # 替换模板中的占位符
        pattern = f"{key}=.*"
        replacement = f"{key}={value}"
        
        import re
        final_content = re.sub(pattern, replacement, final_content)
    
    # 写入配置文件
    try:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        # 设置文件权限 (仅用户可读写)
        os.chmod(env_file, 0o600)
        
        print(f"\n✅ 配置文件已生成: {env_file}")
        print(f"🔒 文件权限已设置为仅用户访问")
        
        # 显示配置摘要
        print(f"\n📋 配置摘要:")
        configured_apis = [api for api in api_keys.keys() if api in user_values]
        if configured_apis:
            print(f"   ✅ 已配置API: {', '.join([api_keys[api]['name'] for api in configured_apis])}")
        else:
            print(f"   ⚠️  未配置任何API密钥，需要手动编辑配置文件")
        
        if 'DATABASE_URL' in user_values:
            print(f"   ✅ 数据库: 已配置")
        else:
            print(f"   📊 数据库: 使用默认SQLite")
        
        print(f"\n🚀 下一步:")
        print(f"   1. 检查配置文件: {env_file}")
        print(f"   2. 启动Qdrant服务 (如果需要)")
        print(f"   3. 运行测试验证配置")
        
    except Exception as e:
        print(f"\n❌ 配置文件生成失败: {e}")
        sys.exit(1)

def validate_api_key(key_name: str, value: str) -> bool:
    """验证API密钥格式"""
    if not value:
        return False
    
    # 基本格式检查
    patterns = {
        'OPENAI_API_KEY': r'^sk-[A-Za-z0-9\-_]{40,}$',
        'ANTHROPIC_API_KEY': r'^sk-ant-[A-Za-z0-9\-_]{40,}$', 
        'GOOGLE_API_KEY': r'^AIza[A-Za-z0-9\-_]{35}$',
        'OPENROUTER_API_KEY': r'^sk-or-[A-Za-z0-9\-_]{40,}$',
        'SILICONFLOW_API_KEY': r'^sk-[A-Za-z0-9\-_]{40,}$'
    }
    
    pattern = patterns.get(key_name)
    if pattern:
        import re
        return bool(re.match(pattern, value))
    
    # 如果没有特定模式，检查最小长度
    return len(value) >= 20

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n🚫 配置已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 配置过程出错: {e}")
        sys.exit(1)