-- Claude Memory 数据库迁移脚本
-- 添加project_id列到现有表
-- 执行时间: 2025-07-11

-- 1. 为conversations表添加project_id列
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) NOT NULL DEFAULT 'global';

-- 2. 为memory_units表添加project_id列
ALTER TABLE memory_units 
ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) NOT NULL DEFAULT 'global';

-- 3. 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_conversations_project_id 
ON conversations(project_id);

CREATE INDEX IF NOT EXISTS idx_conversations_project_started 
ON conversations(project_id, started_at);

CREATE INDEX IF NOT EXISTS idx_memory_units_project_id 
ON memory_units(project_id);

CREATE INDEX IF NOT EXISTS idx_memory_units_project_type_created 
ON memory_units(project_id, unit_type, created_at);

-- 4. 更新现有数据（如果需要）
-- 将所有现有记录的project_id设置为'global'
UPDATE conversations SET project_id = 'global' WHERE project_id IS NULL;
UPDATE memory_units SET project_id = 'global' WHERE project_id IS NULL;

-- 5. 添加注释
COMMENT ON COLUMN conversations.project_id IS '项目ID，使用global实现跨项目共享';
COMMENT ON COLUMN memory_units.project_id IS '项目ID，使用global实现跨项目共享';