-- 添加 project_id 列到 memory_units 表
-- 用于支持跨项目记忆搜索功能

-- 1. 添加 project_id 列
ALTER TABLE memory_units 
ADD COLUMN IF NOT EXISTS project_id VARCHAR(255);

-- 2. 为现有记录设置默认值（从关联的conversation获取）
UPDATE memory_units mu
SET project_id = COALESCE(c.project_id, 'default')
FROM conversations c
WHERE mu.conversation_id = c.id
AND mu.project_id IS NULL;

-- 3. 为没有关联conversation的记录设置默认值
UPDATE memory_units
SET project_id = 'default'
WHERE project_id IS NULL;

-- 4. 设置非空约束
ALTER TABLE memory_units
ALTER COLUMN project_id SET NOT NULL;

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS ix_memory_units_project_id ON memory_units(project_id);

-- 6. 创建组合索引用于跨项目搜索优化
CREATE INDEX IF NOT EXISTS ix_memory_units_project_id_unit_type ON memory_units(project_id, unit_type);