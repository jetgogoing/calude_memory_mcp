-- Claude Memory MCP Service - 创建所有表结构
-- 包含project_id字段的完整表结构

-- 1. 创建conversations表
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL DEFAULT 'default',
    session_id VARCHAR(255),
    title VARCHAR(500) NOT NULL DEFAULT '',
    started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITHOUT TIME ZONE,
    message_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    metadata JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- conversations索引
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_started_at ON conversations(started_at);
CREATE INDEX IF NOT EXISTS idx_conversations_project_id ON conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_conversations_project_started ON conversations(project_id, started_at);

-- 2. 创建messages表
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER NOT NULL DEFAULT 0,
    metadata JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- messages索引
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(message_type);

-- 3. 创建memory_units表
CREATE TABLE IF NOT EXISTS memory_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL DEFAULT 'default',
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    unit_type VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords JSON,
    relevance_score FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    metadata JSON,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- memory_units索引
CREATE INDEX IF NOT EXISTS idx_memory_units_conversation_id ON memory_units(conversation_id);
CREATE INDEX IF NOT EXISTS idx_memory_units_type ON memory_units(unit_type);
CREATE INDEX IF NOT EXISTS idx_memory_units_created_at ON memory_units(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_units_active ON memory_units(is_active);
CREATE INDEX IF NOT EXISTS idx_memory_units_project_id ON memory_units(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_units_project_type_created ON memory_units(project_id, unit_type, created_at);

-- 4. 创建embeddings表
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_unit_id UUID NOT NULL REFERENCES memory_units(id) ON DELETE CASCADE,
    vector JSON NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- embeddings索引
CREATE INDEX IF NOT EXISTS idx_embeddings_memory_unit_id ON embeddings(memory_unit_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_name);

-- 5. 创建cost_tracking表
CREATE TABLE IF NOT EXISTS cost_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL DEFAULT 'default',
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd FLOAT NOT NULL DEFAULT 0.0,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- cost_tracking索引
CREATE INDEX IF NOT EXISTS idx_cost_tracking_provider ON cost_tracking(provider);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_model ON cost_tracking(model_name);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_project_id ON cost_tracking(project_id);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_timestamp ON cost_tracking(timestamp);

-- 6. 创建projects表（如果不存在）
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    settings JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- projects索引
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);

-- 7. 插入默认项目（如果不存在）
INSERT INTO projects (id, name, description, settings)
VALUES ('default', '默认项目', '系统默认项目，用于未指定项目的记忆', '{}')
ON CONFLICT (id) DO NOTHING;

-- 8. 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 9. 为相关表创建更新时间触发器
DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE
ON conversations FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_memory_units_updated_at ON memory_units;
CREATE TRIGGER update_memory_units_updated_at BEFORE UPDATE
ON memory_units FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE
ON projects FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- 10. 创建项目统计视图
CREATE OR REPLACE VIEW project_statistics AS
SELECT 
    p.id as project_id,
    p.name as project_name,
    COUNT(DISTINCT c.id) as conversation_count,
    COUNT(DISTINCT mu.id) as memory_unit_count,
    COALESCE(SUM(c.token_count), 0) as total_tokens,
    MAX(c.started_at) as last_activity,
    p.created_at as project_created_at
FROM projects p
LEFT JOIN conversations c ON p.id = c.project_id
LEFT JOIN memory_units mu ON p.id = mu.project_id
WHERE p.is_active = TRUE
GROUP BY p.id, p.name, p.created_at;

-- 添加注释
COMMENT ON TABLE conversations IS '对话记录表';
COMMENT ON TABLE messages IS '消息记录表';
COMMENT ON TABLE memory_units IS '记忆单元表';
COMMENT ON TABLE embeddings IS '向量嵌入表';
COMMENT ON TABLE cost_tracking IS '成本追踪表';
COMMENT ON TABLE projects IS '项目配置表';
COMMENT ON VIEW project_statistics IS '项目统计视图';

COMMENT ON COLUMN conversations.project_id IS '项目ID，用于跨项目记忆隔离';
COMMENT ON COLUMN memory_units.project_id IS '项目ID，用于跨项目记忆隔离';
COMMENT ON COLUMN cost_tracking.project_id IS '项目ID，用于成本追踪';