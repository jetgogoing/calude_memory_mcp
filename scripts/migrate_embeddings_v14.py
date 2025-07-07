#!/usr/bin/env python3
"""
Claude记忆管理MCP服务 - v1.4数据迁移脚本

功能：
1. 从旧集合(claude_memory_vectors, 1536维)迁移到新集合(claude_memory_vectors_v14, 4096维)
2. 使用Qwen3-Embedding-8B重新生成所有记忆单元的向量表示
3. 支持断点续传和错误恢复
4. 提供详细的进度报告和数据完整性验证

用法：
    python scripts/migrate_embeddings_v14.py [--dry-run] [--resume] [--batch-size 100]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import ResponseHandlingException
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_memory.config.settings import get_settings
from claude_memory.models.data_models import MemoryUnitDB, EmbeddingDB
from claude_memory.utils.model_manager import ModelManager
from claude_memory.utils.cost_tracker import CostTracker


class MigrationProgress(BaseModel):
    """迁移进度跟踪"""
    
    total_memory_units: int = 0
    processed_memory_units: int = 0
    successfully_migrated: int = 0
    failed_migrations: int = 0
    skipped_memory_units: int = 0
    last_processed_id: Optional[str] = None
    migration_start_time: Optional[datetime] = None
    estimated_completion_time: Optional[datetime] = None
    total_cost_usd: float = 0.0
    errors: List[Dict] = []


class EmbeddingMigrator:
    """向量迁移器"""
    
    def __init__(self, dry_run: bool = False, batch_size: int = 100):
        self.settings = get_settings()
        self.dry_run = dry_run
        self.batch_size = batch_size
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = structlog.get_logger(__name__)
        
        # 初始化组件
        self.model_manager = None
        self.cost_tracker = CostTracker()
        self.old_qdrant_client = None
        self.new_qdrant_client = None
        self.db_session = None
        
        # 进度跟踪
        self.progress = MigrationProgress()
        self.progress_file = Path("migration_progress_v14.json")
        
        # 集合配置
        self.old_collection_name = "claude_memory_vectors"  # 1536维
        self.new_collection_name = self.settings.qdrant.collection_name  # claude_memory_vectors_v14, 4096维
        
        self.logger.info(
            "Migration initialized",
            dry_run=self.dry_run,
            batch_size=self.batch_size,
            old_collection=self.old_collection_name,
            new_collection=self.new_collection_name
        )
    
    async def initialize(self) -> None:
        """初始化所有连接和组件"""
        try:
            # 初始化ModelManager
            self.model_manager = ModelManager()
            await self.model_manager.initialize()
            
            # 初始化Qdrant客户端
            self.old_qdrant_client = QdrantClient(
                host=self.settings.qdrant.qdrant_url.split("://")[1].split(":")[0],
                port=int(self.settings.qdrant.qdrant_url.split(":")[-1]),
                api_key=self.settings.qdrant.api_key,
                timeout=self.settings.qdrant.timeout
            )
            
            self.new_qdrant_client = QdrantClient(
                host=self.settings.qdrant.qdrant_url.split("://")[1].split(":")[0],
                port=int(self.settings.qdrant.qdrant_url.split(":")[-1]),
                api_key=self.settings.qdrant.api_key,
                timeout=self.settings.qdrant.timeout
            )
            
            # 初始化数据库会话
            if self.settings.database.database_url.startswith("sqlite"):
                # SQLite异步连接
                engine = create_async_engine(
                    self.settings.database.database_url.replace("sqlite://", "sqlite+aiosqlite://")
                )
            else:
                # PostgreSQL异步连接
                database_url = self.settings.database.database_url.replace("postgresql://", "postgresql+asyncpg://")
                engine = create_async_engine(database_url)
            
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            self.db_session = async_session()
            
            self.logger.info("Migration components initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize migration components", error=str(e))
            raise
    
    async def verify_prerequisites(self) -> bool:
        """验证迁移前提条件"""
        try:
            # 检查旧集合是否存在
            old_collections = self.old_qdrant_client.get_collections()
            old_collection_exists = any(
                col.name == self.old_collection_name 
                for col in old_collections.collections
            )
            
            if not old_collection_exists:
                self.logger.warning(
                    "Old collection not found, will migrate from database only",
                    collection=self.old_collection_name
                )
            
            # 检查新集合，如果不存在则创建
            new_collections = self.new_qdrant_client.get_collections()
            new_collection_exists = any(
                col.name == self.new_collection_name 
                for col in new_collections.collections
            )
            
            if not new_collection_exists:
                self.logger.info("Creating new collection", collection=self.new_collection_name)
                
                if not self.dry_run:
                    self.new_qdrant_client.create_collection(
                        collection_name=self.new_collection_name,
                        vectors_config=qdrant_models.VectorParams(
                            size=self.settings.qdrant.vector_size,  # 4096
                            distance=qdrant_models.Distance.COSINE
                        )
                    )
                    self.logger.info("New collection created successfully")
            
            # 检查数据库连接
            result = await self.db_session.execute(text("SELECT COUNT(*) FROM memory_units"))
            total_memory_units = result.scalar()
            
            self.progress.total_memory_units = total_memory_units
            self.logger.info(
                "Prerequisites verified",
                total_memory_units=total_memory_units,
                old_collection_exists=old_collection_exists,
                new_collection_exists=new_collection_exists
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Prerequisites verification failed", error=str(e))
            return False
    
    def load_progress(self) -> bool:
        """加载迁移进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    self.progress = MigrationProgress(**progress_data)
                    
                self.logger.info(
                    "Migration progress loaded",
                    processed=self.progress.processed_memory_units,
                    total=self.progress.total_memory_units,
                    last_id=self.progress.last_processed_id
                )
                return True
                
            except Exception as e:
                self.logger.error("Failed to load progress", error=str(e))
                return False
        return False
    
    def save_progress(self) -> None:
        """保存迁移进度"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress.dict(), f, indent=2, default=str)
                
        except Exception as e:
            self.logger.error("Failed to save progress", error=str(e))
    
    async def migrate_memory_units(self, resume: bool = False) -> None:
        """迁移记忆单元"""
        
        if resume and self.load_progress():
            start_id = self.progress.last_processed_id
            self.logger.info("Resuming migration", start_id=start_id)
        else:
            start_id = None
            self.progress.migration_start_time = datetime.utcnow()
        
        # 查询需要迁移的记忆单元
        query = """
            SELECT id, conversation_id, unit_type, title, summary, content, 
                   keywords, metadata, created_at, updated_at
            FROM memory_units 
            WHERE is_active = true
        """
        
        if start_id:
            query += f" AND id > '{start_id}'"
        
        query += " ORDER BY id"
        
        result = await self.db_session.execute(text(query))
        memory_units = result.fetchall()
        
        self.logger.info(f"Found {len(memory_units)} memory units to migrate")
        
        # 分批处理
        with tqdm(total=len(memory_units), desc="Migrating memory units") as pbar:
            for i in range(0, len(memory_units), self.batch_size):
                batch = memory_units[i:i + self.batch_size]
                await self._process_batch(batch, pbar)
                
                # 保存进度
                self.save_progress()
        
        self.logger.info(
            "Migration completed",
            total_processed=self.progress.processed_memory_units,
            successful=self.progress.successfully_migrated,
            failed=self.progress.failed_migrations,
            skipped=self.progress.skipped_memory_units,
            total_cost=self.progress.total_cost_usd
        )
    
    async def _process_batch(self, batch: List, pbar: tqdm) -> None:
        """处理单个批次"""
        batch_points = []
        
        for memory_unit_row in batch:
            try:
                # 准备文本用于embedding
                text_for_embedding = f"{memory_unit_row.summary} {memory_unit_row.content}"
                
                # 生成新的4096维embedding
                if not self.dry_run:
                    embedding_vector = await self._generate_embedding(text_for_embedding)
                    
                    # 计算成本
                    cost = self.cost_tracker.calculate_cost(
                        self.settings.models.default_embedding_model,
                        len(text_for_embedding.split()) * 1.3,  # 估算token数
                        0
                    )
                    self.progress.total_cost_usd += cost
                else:
                    # 干跑模式，使用假向量
                    embedding_vector = [0.0] * self.settings.qdrant.vector_size
                
                # 构建Qdrant点
                metadata = {
                    'id': str(memory_unit_row.id),
                    'conversation_id': str(memory_unit_row.conversation_id),
                    'unit_type': memory_unit_row.unit_type,
                    'title': memory_unit_row.title,
                    'keywords': memory_unit_row.keywords if memory_unit_row.keywords else [],
                    'created_at': memory_unit_row.created_at.isoformat(),
                    'migration_timestamp': datetime.utcnow().isoformat(),
                }
                
                point = qdrant_models.PointStruct(
                    id=str(memory_unit_row.id),
                    vector=embedding_vector,
                    payload=metadata
                )
                
                batch_points.append(point)
                self.progress.last_processed_id = str(memory_unit_row.id)
                
            except Exception as e:
                self.logger.error(
                    "Failed to process memory unit",
                    memory_unit_id=str(memory_unit_row.id),
                    error=str(e)
                )
                self.progress.failed_migrations += 1
                self.progress.errors.append({
                    'memory_unit_id': str(memory_unit_row.id),
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
                continue
        
        # 批量上传到新集合
        if batch_points and not self.dry_run:
            try:
                await self.new_qdrant_client.upsert(
                    collection_name=self.new_collection_name,
                    points=batch_points
                )
                self.progress.successfully_migrated += len(batch_points)
                
            except Exception as e:
                self.logger.error("Failed to upsert batch", error=str(e))
                self.progress.failed_migrations += len(batch_points)
        
        elif self.dry_run:
            self.progress.successfully_migrated += len(batch_points)
        
        # 更新进度条
        self.progress.processed_memory_units += len(batch)
        pbar.update(len(batch))
        
        # 显示进度信息
        pbar.set_postfix({
            'Success': self.progress.successfully_migrated,
            'Failed': self.progress.failed_migrations,
            'Cost': f"${self.progress.total_cost_usd:.4f}"
        })
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """生成embedding向量"""
        try:
            # 调用ModelManager生成embedding
            embedding_response = await self.model_manager.generate_embedding(
                model=self.settings.models.default_embedding_model,
                text=text
            )
            
            if hasattr(embedding_response, 'embedding'):
                return embedding_response.embedding
            elif isinstance(embedding_response, dict) and 'embedding' in embedding_response:
                return embedding_response['embedding']
            elif isinstance(embedding_response, list):
                return embedding_response
            else:
                raise ValueError(f"Unexpected embedding response format: {type(embedding_response)}")
                
        except Exception as e:
            self.logger.error("Failed to generate embedding", error=str(e))
            raise
    
    async def validate_migration(self) -> bool:
        """验证迁移结果"""
        try:
            # 检查新集合中的点数
            collection_info = await self.new_qdrant_client.get_collection(self.new_collection_name)
            points_count = collection_info.points_count
            
            # 检查数据库中的记忆单元数
            result = await self.db_session.execute(
                text("SELECT COUNT(*) FROM memory_units WHERE is_active = true")
            )
            db_count = result.scalar()
            
            self.logger.info(
                "Migration validation",
                qdrant_points=points_count,
                db_memory_units=db_count,
                migration_successful=self.progress.successfully_migrated,
                migration_failed=self.progress.failed_migrations
            )
            
            # 随机抽样验证
            if points_count > 0:
                sample_points = await self.new_qdrant_client.scroll(
                    collection_name=self.new_collection_name,
                    limit=min(10, points_count),
                    with_payload=True,
                    with_vectors=True
                )
                
                for point in sample_points[0]:
                    vector_dim = len(point.vector)
                    if vector_dim != self.settings.qdrant.vector_size:
                        self.logger.error(
                            "Vector dimension mismatch",
                            expected=self.settings.qdrant.vector_size,
                            actual=vector_dim,
                            point_id=point.id
                        )
                        return False
                
                self.logger.info("Sample validation passed", sample_size=len(sample_points[0]))
            
            return points_count == self.progress.successfully_migrated
            
        except Exception as e:
            self.logger.error("Migration validation failed", error=str(e))
            return False
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            if self.model_manager:
                await self.model_manager.close()
            
            if self.db_session:
                await self.db_session.close()
            
            if hasattr(self.old_qdrant_client, 'close'):
                await self.old_qdrant_client.close()
            
            if hasattr(self.new_qdrant_client, 'close'):
                await self.new_qdrant_client.close()
                
        except Exception as e:
            self.logger.error("Cleanup failed", error=str(e))


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Migrate embeddings from v1.3 to v1.4")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actual migration")
    parser.add_argument("--resume", action="store_true", help="Resume from last saved progress")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing migration")
    
    args = parser.parse_args()
    
    migrator = EmbeddingMigrator(
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
    
    try:
        await migrator.initialize()
        
        if not await migrator.verify_prerequisites():
            print("❌ Prerequisites verification failed")
            return 1
        
        if args.validate_only:
            if await migrator.validate_migration():
                print("✅ Migration validation passed")
                return 0
            else:
                print("❌ Migration validation failed")
                return 1
        
        print(f"🚀 Starting migration (dry_run={args.dry_run})")
        await migrator.migrate_memory_units(resume=args.resume)
        
        if await migrator.validate_migration():
            print("✅ Migration completed and validated successfully")
            
            # 清理进度文件
            if migrator.progress_file.exists():
                migrator.progress_file.unlink()
                
            return 0
        else:
            print("❌ Migration validation failed")
            return 1
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1
        
    finally:
        await migrator.cleanup()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))