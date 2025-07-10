#!/usr/bin/env python3
"""
数据库简化脚本 - 移除项目隔离，统一全局记忆
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncpg
from claude_memory.config.settings import get_settings
from claude_memory.processors.semantic_compressor import SemanticCompressor, CompressionRequest
from claude_memory.models.data_models import ConversationModel, MessageModel, MemoryUnitModel
import structlog

logger = structlog.get_logger(__name__)

async def migrate_to_global():
    """执行数据库迁移到全局项目"""
    settings = get_settings()
    
    # 连接数据库
    conn = await asyncpg.connect(settings.database.database_url)
    
    try:
        # 1. 备份当前数据统计
        print("\n=== 当前数据统计 ===")
        
        # 统计各表数据
        conversations_count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        messages_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
        memory_units_count = await conn.fetchval("SELECT COUNT(*) FROM memory_units")
        
        print(f"conversations表: {conversations_count} 条记录")
        print(f"messages表: {messages_count} 条记录")
        print(f"memory_units表: {memory_units_count} 条记录")
        
        # 统计项目分布
        project_stats = await conn.fetch("""
            SELECT p.name as project_name, 
                   COUNT(DISTINCT c.id) as conversation_count,
                   COUNT(DISTINCT m.id) as memory_unit_count
            FROM projects p
            LEFT JOIN conversations c ON c.project_id = p.id
            LEFT JOIN memory_units m ON m.project_id = p.id
            GROUP BY p.id, p.name
            ORDER BY p.name
        """)
        
        print("\n项目分布:")
        for stat in project_stats:
            print(f"  - {stat['project_name']}: {stat['conversation_count']} 对话, {stat['memory_unit_count']} 记忆单元")
        
        # 2. 获取或创建 global 项目
        global_project = await conn.fetchrow("SELECT id FROM projects WHERE name = 'global'")
        if not global_project:
            global_project_id = await conn.fetchval("""
                INSERT INTO projects (id, name, description, is_active, created_at, updated_at)
                VALUES (gen_random_uuid(), 'global', '全局共享记忆项目', true, NOW(), NOW())
                RETURNING id
            """)
            print(f"\n创建 global 项目: {global_project_id}")
        else:
            global_project_id = global_project['id']
            print(f"\n使用现有 global 项目: {global_project_id}")
        
        # 3. 将所有对话迁移到 global 项目
        print("\n=== 开始迁移对话到 global 项目 ===")
        
        # 先更新，再查询数量
        await conn.execute("""
            UPDATE conversations 
            SET project_id = $1, updated_at = NOW()
            WHERE project_id != $1
        """, global_project_id)
        
        updated_conversations = await conn.fetchval("""
            SELECT COUNT(*) FROM conversations WHERE project_id = $1
        """, global_project_id)
        
        print(f"已迁移 {updated_conversations or 0} 个对话到 global 项目")
        
        # 4. 将所有 memory_units 迁移到 global 项目
        # 先更新，再查询数量
        await conn.execute("""
            UPDATE memory_units 
            SET project_id = $1, updated_at = NOW()
            WHERE project_id != $1
        """, global_project_id)
        
        updated_memory_units = await conn.fetchval("""
            SELECT COUNT(*) FROM memory_units WHERE project_id = $1
        """, global_project_id)
        
        print(f"已迁移 {updated_memory_units or 0} 个记忆单元到 global 项目")
        
        # 5. 删除其他项目
        deleted_projects = await conn.fetch("""
            DELETE FROM projects 
            WHERE name != 'global'
            RETURNING name
        """)
        
        if deleted_projects:
            print(f"\n删除的项目: {[p['name'] for p in deleted_projects]}")
        
        # 6. 删除 cost_tracking 表
        print("\n=== 删除无用表 ===")
        await conn.execute("DROP TABLE IF EXISTS cost_tracking CASCADE")
        print("已删除 cost_tracking 表")
        
        # 7. 检查是否有对话没有对应的 memory_units
        print("\n=== 检查缺失的记忆单元 ===")
        
        missing_memory_conversations = await conn.fetch("""
            SELECT c.id, c.title, c.created_at, COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE NOT EXISTS (
                SELECT 1 FROM memory_units mu 
                WHERE mu.conversation_id = c.id
            )
            GROUP BY c.id, c.title, c.created_at
            HAVING COUNT(m.id) > 0
            ORDER BY c.created_at DESC
        """)
        
        print(f"发现 {len(missing_memory_conversations)} 个对话没有生成记忆单元")
        
        if missing_memory_conversations:
            print("\n需要生成记忆单元的对话:")
            for conv in missing_memory_conversations[:10]:  # 只显示前10个
                print(f"  - ID: {conv['id']}, 标题: {conv['title']}, 消息数: {conv['message_count']}")
            
            if len(missing_memory_conversations) > 10:
                print(f"  ... 还有 {len(missing_memory_conversations) - 10} 个对话")
        
        # 8. 自动生成记忆单元
        if missing_memory_conversations:
            print("\n自动为这些对话生成记忆单元...")
            await generate_missing_memory_units(conn, missing_memory_conversations, global_project_id)
        
        print("\n=== 迁移完成 ===")
        
    finally:
        await conn.close()


async def generate_missing_memory_units(conn, conversations, project_id):
    """为缺失的对话生成记忆单元"""
    print("\n开始生成记忆单元...")
    
    # 初始化压缩器
    compressor = SemanticCompressor()
    
    success_count = 0
    error_count = 0
    
    for i, conv_info in enumerate(conversations):
        try:
            print(f"\n处理对话 {i+1}/{len(conversations)}: {conv_info['title']}")
            
            # 获取完整的对话数据
            messages = await conn.fetch("""
                SELECT id, message_type, content, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """, conv_info['id'])
            
            if not messages:
                print(f"  跳过：没有消息")
                continue
            
            # 构建对话模型
            conversation = ConversationModel(
                id=str(conv_info['id']),
                project_id=str(project_id),
                title=conv_info['title'] or "未命名对话",
                messages=[
                    MessageModel(
                        id=str(msg['id']),
                        conversation_id=str(conv_info['id']),
                        message_type=msg['message_type'],
                        content=msg['content'],
                        timestamp=msg['created_at']
                    )
                    for msg in messages
                ],
                created_at=conv_info['created_at']
            )
            
            # 创建压缩请求
            request = CompressionRequest(conversation=conversation)
            
            # 执行压缩
            result = await compressor.compress_conversation(request)
            
            # 保存记忆单元到数据库
            await conn.execute("""
                INSERT INTO memory_units (
                    id, project_id, conversation_id, content, summary, 
                    title, unit_type, relevance_score, token_count,
                    is_active, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, 
                    $5, $6, $7, $8, 
                    true, NOW(), NOW()
                )
            """, 
                project_id,
                conv_info['id'],
                result.memory_unit.content,
                result.memory_unit.summary or result.memory_unit.content[:200],
                conv_info['title'] or "对话记忆",
                result.memory_unit.unit_type.value,
                result.memory_unit.importance_score,
                result.memory_unit.token_count
            )
            
            print(f"  ✓ 成功生成记忆单元")
            success_count += 1
            
        except Exception as e:
            print(f"  ✗ 错误: {str(e)}")
            error_count += 1
            
    print(f"\n生成完成: 成功 {success_count}, 失败 {error_count}")


async def main():
    """主函数"""
    print("=== Claude Memory 数据库简化工具 ===")
    print("此工具将：")
    print("1. 将所有对话和记忆迁移到 global 项目")
    print("2. 删除其他测试项目")
    print("3. 删除 cost_tracking 表")
    print("4. 为缺失的对话生成记忆单元")
    
    # 自动执行，不需要确认
    print("\n开始执行...")
    
    await migrate_to_global()


if __name__ == "__main__":
    asyncio.run(main())