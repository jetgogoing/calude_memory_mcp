-- 修复数据问题的SQL脚本

-- 1. 手动添加测试数据
INSERT INTO memory_units (
    id,
    project_id, 
    conversation_id, 
    unit_type, 
    title, 
    summary, 
    content, 
    keywords,
    relevance_score,
    token_count,
    created_at
) VALUES (
    gen_random_uuid(),
    'default',
    '02177d43-864f-4a38-9d9e-f85abc800c40'::uuid,
    'conversation',
    'UpdateResult错误讨论',
    'UpdateResult错误通常出现在异步编程中，特别是使用asyncio库时。这个错误表示一个协程或Future对象没有被正确等待或处理。',
    '用户询问了什么是UpdateResult错误以及在什么情况下会出现。助手解释了这是异步编程中的常见错误，通常因为忘记使用await关键字、异步函数返回值处理不当或事件循环管理问题导致。解决方法是确保所有异步调用都被正确await，并检查异步上下文管理。',
    '["UpdateResult错误", "asyncio", "异步编程", "协程", "await", "Future", "事件循环"]'::jsonb,
    0.95,
    200,
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- 2. 验证插入结果
SELECT id, project_id, title, keywords 
FROM memory_units 
WHERE project_id = 'default' 
  AND (title LIKE '%UpdateResult%' OR keywords::text LIKE '%UpdateResult%')
ORDER BY created_at DESC
LIMIT 5;