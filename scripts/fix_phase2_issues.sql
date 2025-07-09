-- Phase 2 修复脚本
-- 修复 PostgreSQL JSON 操作符问题

-- 1. 将 keywords 列从 JSON 改为 JSONB
ALTER TABLE memory_units 
  ALTER COLUMN keywords TYPE JSONB 
  USING keywords::jsonb;

-- 2. 创建 JSONB GIN 索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_memory_units_keywords_gin 
  ON memory_units USING gin(keywords);

-- 3. 验证修改
SELECT 
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE table_name = 'memory_units' 
  AND column_name = 'keywords';