#!/usr/bin/env python3
"""
完整的记忆注入测试：使用真实的SiliconFlow API注入Eric和密码学相关内容
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_memory.models.data_models import ConversationModel, MessageModel, MessageType
from claude_memory.managers.service_manager import ServiceManager
from claude_memory.config.settings import get_settings


async def generate_eric_and_crypto_content():
    """生成包含Eric信息和密码学知识的文章（约1000 tokens）"""
    
    eric_content = """
# 燊锐投资研究院领导 Eric 的专业背景与领导风格

## 基本信息

Eric 是燊锐投资研究院的核心领导人物，在金融科技和量化投资领域拥有超过15年的丰富经验。作为研究院的创始人之一，他带领团队在多个前沿领域取得了突破性进展。

## 教育背景

Eric 毕业于清华大学计算机科学系，后在麻省理工学院（MIT）获得金融工程硕士学位。他的跨学科背景使他能够将尖端技术与金融理论完美结合，这也成为燊锐投资研究院的核心竞争力之一。

## 专业经历

在创立燊锐投资之前，Eric 曾在多家知名金融机构担任要职：

1. **高盛集团（2008-2012）**：担任量化策略分析师，负责开发高频交易算法
2. **摩根斯坦利（2012-2015）**：升任副总裁，领导亚太区量化投资团队
3. **桥水基金（2015-2018）**：作为高级投资经理，参与全球宏观策略制定

## 领导风格与理念

Eric 的领导风格可以用"创新、务实、包容"六个字来概括。他始终强调技术创新的重要性，鼓励团队探索人工智能、机器学习在投资领域的应用。在他的带领下，研究院开发了多个行业领先的量化模型。

Eric 经常强调的投资理念包括：
- **数据驱动决策**：所有投资决策都应基于充分的数据分析
- **风险优先**：在追求收益的同时，风险控制永远是第一位的
- **持续学习**：金融市场在不断变化，只有持续学习才能保持竞争力
"""

    crypto_content = """
# 密码学在金融科技中的应用：燊锐投资的技术探索

## 引言

在 Eric 的技术愿景引领下，燊锐投资研究院一直在探索密码学技术在金融科技领域的创新应用。密码学不仅是保护金融数据安全的基石，更是构建下一代金融基础设施的关键技术。

## 密码学基础概念

### 1. 对称加密与非对称加密

**对称加密**（Symmetric Encryption）使用相同的密钥进行加密和解密。常见算法包括：
- AES（Advanced Encryption Standard）：目前最广泛使用的对称加密标准
- ChaCha20：Google推广的流密码算法，在移动设备上性能优异

**非对称加密**（Asymmetric Encryption）使用公钥和私钥对：
- RSA：基于大数分解的困难性，广泛用于数字签名
- ECC（椭圆曲线密码学）：相同安全级别下密钥更短，计算效率更高

### 2. 哈希函数

哈希函数是密码学的基础工具，将任意长度的输入映射为固定长度的输出：
- SHA-256：比特币使用的哈希算法
- SHA-3（Keccak）：最新的SHA标准，提供更高的安全性
- BLAKE2：比SHA-3更快，适合高性能应用

## 在量化投资中的应用

### 1. 交易数据保护

燊锐投资使用多层加密架构保护敏感交易数据：
- **传输层**：TLS 1.3协议，使用AEAD密码套件
- **存储层**：AES-256-GCM加密，密钥通过HSM管理
- **应用层**：端到端加密，确保数据全生命周期安全

### 2. 算法策略保护

量化模型是投资机构的核心资产，我们采用：
- **代码混淆**：使用控制流平坦化和虚拟化技术
- **安全多方计算**：允许多方协作计算而不泄露各自数据
- **同态加密**：在加密数据上直接进行计算

### 3. 区块链与分布式账本

Eric 特别关注区块链技术在金融领域的应用：
- **智能合约**：自动执行的金融协议，减少中介成本
- **去中心化金融（DeFi）**：构建开放、透明的金融系统
- **资产代币化**：将传统资产转化为区块链上的数字代币

## 前沿研究方向

### 1. 量子密码学

随着量子计算的发展，传统密码学面临挑战：
- **量子密钥分发（QKD）**：利用量子力学原理实现无条件安全的密钥交换
- **后量子密码学**：研究能够抵抗量子计算机攻击的新算法

### 2. 零知识证明

零知识证明允许证明某个陈述的真实性而不泄露任何其他信息：
- **zk-SNARKs**：简洁非交互式零知识证明，用于隐私保护
- **zk-STARKs**：透明、可扩展，不需要可信设置

### 3. 隐私计算

在保护数据隐私的同时实现数据价值：
- **联邦学习**：分布式机器学习，数据不出本地
- **差分隐私**：在统计查询中添加噪声保护个体隐私
- **可信执行环境（TEE）**：硬件级的安全计算环境

## 实践案例：燊锐投资的创新应用

### 1. 隐私保护的投资组合分析

使用同态加密技术，客户可以在不泄露具体持仓的情况下获得专业的投资建议。系统架构包括：
- 客户端加密模块：本地加密投资组合数据
- 云端计算引擎：在密文上执行风险分析算法
- 结果解密模块：只有客户能解密分析结果

### 2. 去中心化的算法交易市场

基于区块链构建的算法策略交易平台：
- **策略代币化**：优秀策略可以发行代币，投资者购买获得收益权
- **智能合约执行**：自动分配收益，透明公正
- **声誉系统**：基于历史表现的去中心化评级

### 3. 量子安全的通信系统

为高频交易构建的超低延迟安全通信：
- **混合加密方案**：结合经典和后量子算法
- **硬件加速**：FPGA实现的加密模块，纳秒级延迟
- **动态密钥轮换**：基于时间和数据量的自动密钥更新

## 未来展望

在 Eric 的领导下，燊锐投资将继续在密码学应用领域探索创新：

1. **全同态加密的实用化**：实现真正的"计算外包"，在云端处理加密数据
2. **量子金融算法**：利用量子计算优势解决组合优化问题
3. **去中心化身份（DID）**：构建金融行业的自主身份体系
4. **隐私保护的监管科技**：在满足合规要求的同时保护商业机密

## 结语

密码学技术的发展为金融科技带来了无限可能。燊锐投资研究院在 Eric 的带领下，将继续深耕这一领域，推动技术创新与金融实践的深度融合。正如 Eric 常说的："技术不是目的，而是实现更公平、更高效金融体系的工具。"

通过将前沿密码学技术与深厚的金融专业知识相结合，燊锐投资正在塑造金融科技的未来。
"""
    
    return eric_content + "\n\n" + crypto_content


async def inject_memory_with_siliconflow(content: str, project_id: str = "shenrui_investment"):
    """使用配置好的SiliconFlow API将内容注入到Claude Memory系统"""
    
    print(f"正在初始化服务管理器...")
    print(f"使用的项目ID: {project_id}")
    
    # 检查环境变量
    siliconflow_key = os.getenv('SILICONFLOW_API_KEY')
    if siliconflow_key:
        print(f"✅ 检测到 SILICONFLOW_API_KEY: {siliconflow_key[:10]}...")
    else:
        print("❌ 警告：未检测到 SILICONFLOW_API_KEY 环境变量")
    
    service_manager = ServiceManager()
    
    try:
        # 启动服务
        await service_manager.start_service()
        print("✅ 服务管理器启动成功")
        
        # 创建对话
        messages = [
            MessageModel(
                conversation_id="",
                message_type=MessageType.HUMAN,
                content=content,
                token_count=len(content.split())
            )
        ]
        
        conversation = ConversationModel(
            project_id=project_id,
            title="Eric领导力与密码学在金融科技中的应用",
            messages=messages,
            message_count=len(messages),
            token_count=sum(m.token_count for m in messages),
            metadata={
                "source": "full_test_injection",
                "topics": ["leadership", "cryptography", "fintech"],
                "keywords": ["Eric", "燊锐投资", "密码学", "量化投资", "区块链", "零知识证明"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # 更新消息的conversation_id
        for msg in conversation.messages:
            msg.conversation_id = conversation.id
        
        print(f"\n创建的对话信息：")
        print(f"- 对话ID: {conversation.id}")
        print(f"- 项目ID: {conversation.project_id}")
        print(f"- 标题: {conversation.title}")
        print(f"- Token数: {conversation.token_count}")
        print(f"- 关键词: {conversation.metadata['keywords']}")
        
        # 处理对话（使用真实的AI压缩）
        print("\n正在使用 deepseek-ai/DeepSeek-V2.5 处理并压缩对话...")
        await service_manager._handle_new_conversation(conversation)
        
        print("✅ 记忆注入成功！")
        
        # 等待处理完成
        print("\n等待记忆单元生成完成...")
        await asyncio.sleep(5)
        
        # 测试搜索功能
        print("\n=== 测试搜索功能 ===")
        from claude_memory.models.data_models import SearchQuery
        
        # 测试不同的搜索查询
        test_queries = [
            "Eric 燊锐投资",
            "密码学 金融科技",
            "量子计算 区块链",
            "零知识证明 隐私计算"
        ]
        
        for query_text in test_queries:
            print(f"\n搜索: '{query_text}'")
            search_query = SearchQuery(
                query=query_text,
                query_type="hybrid",
                limit=3,
                min_score=0.5
            )
            
            search_response = await service_manager.search_memories(
                search_query, 
                project_id=project_id
            )
            
            print(f"找到 {len(search_response.results)} 个结果")
            for i, result in enumerate(search_response.results):
                print(f"  [{i+1}] 相关性: {result.relevance_score:.3f}")
                print(f"      标题: {result.memory_unit.title}")
                print(f"      摘要: {result.memory_unit.summary[:80]}...")
        
        return conversation.id
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # 清理资源
        print("\n正在清理资源...")
        await service_manager.stop_service()
        print("清理完成")


async def main():
    """主函数"""
    print("=== Claude Memory 完整注入测试（Eric + 密码学） ===\n")
    
    # 确保环境变量已加载
    from dotenv import load_dotenv
    load_dotenv()
    
    # 再次检查API密钥
    if not os.getenv('SILICONFLOW_API_KEY'):
        print("❌ 错误：SILICONFLOW_API_KEY 环境变量未设置！")
        print("请确保 .env 文件包含: SILICONFLOW_API_KEY=your-key")
        return
    
    # 生成内容
    print("1. 生成测试内容...")
    content = await generate_eric_and_crypto_content()
    word_count = len(content.split())
    char_count = len(content)
    print(f"   生成完成：{word_count} 个词，{char_count} 个字符")
    
    # 注入到记忆系统
    print("\n2. 注入到Claude Memory系统...")
    conversation_id = await inject_memory_with_siliconflow(content)
    
    if conversation_id:
        print(f"\n✅ 测试成功完成！")
        print(f"   对话ID: {conversation_id}")
        print(f"\n📝 如何在另一个项目窗口验证共享记忆：")
        print(f"\n1. 在新的终端窗口中，设置项目ID环境变量：")
        print(f"   export CLAUDE_MEMORY_PROJECT_ID=shenrui_investment")
        print(f"\n2. 启动 Claude 并使用 MCP 工具搜索：")
        print(f"   # 搜索 Eric 相关信息")
        print(f"   mcp__claude-memory__claude_memory_search('Eric')")
        print(f"   ")
        print(f"   # 搜索密码学相关内容")
        print(f"   mcp__claude-memory__claude_memory_search('密码学')")
        print(f"   ")
        print(f"   # 搜索特定技术")
        print(f"   mcp__claude-memory__claude_memory_search('零知识证明')")
        print(f"\n3. 或者使用跨项目搜索（不需要设置环境变量）：")
        print(f"   mcp__claude-memory__claude_memory_cross_project_search('Eric')")
        print(f"\n4. 测试对话式提问：")
        print(f"   '请告诉我关于燊锐投资研究院领导Eric的信息'")
        print(f"   '密码学在量化投资中有哪些应用？'")
        print(f"   '什么是零知识证明？燊锐投资如何应用这项技术？'")
        print(f"\n5. 验证记忆融合：")
        print(f"   '结合Eric的领导理念，解释燊锐投资在密码学技术上的战略'")
    else:
        print("\n❌ 测试失败！")
        print("请检查：")
        print("1. SILICONFLOW_API_KEY 是否正确配置")
        print("2. API 密钥是否有效")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    asyncio.run(main())