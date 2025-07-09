
-- 修复title字段中的JSON格式
UPDATE memory_units 
SET title = 
    CASE 
        WHEN title LIKE '```json%' THEN 
            (regexp_replace(title, '```json\s*
\s*\{\s*"title"\s*:\s*"([^"]+)".*', '', 's'))::text
        ELSE title
    END
WHERE title LIKE '```json%';

-- 添加一条测试数据供Phase 2使用
INSERT INTO memory_units (
    project_id, 
    conversation_id, 
    unit_type, 
    title, 
    summary, 
    content, 
    keywords,
    relevance_score,
    token_count
) VALUES (
    'default',
    '02177d43-864f-4a38-9d9e-f85abc800c40',
    'conversation',
    'UpdateResult错误讨论',
    'UpdateResult错误通常出现在异步编程中，特别是使用asyncio库时',
    '用户询问了UpdateResult错误的含义和常见原因。助手解释这是异步编程中的常见错误，表示协程未被正确等待。',
    '["UpdateResult错误", "asyncio", "异步编程", "协程", "await"]'::jsonb,
    0.9,
    150
) ON CONFLICT DO NOTHING;

-- 验证修复结果
SELECT project_id, title, keywords FROM memory_units WHERE project_id = 'default' LIMIT 5;
