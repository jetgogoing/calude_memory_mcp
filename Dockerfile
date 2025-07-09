# Claude Memory 全局服务 Docker 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY src/ ./src/
COPY mcp/ ./mcp/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY prompts/ ./prompts/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p logs storage

# 设置环境变量
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# 全局服务默认项目ID
ENV CLAUDE_MEMORY_PROJECT_ID=global

# 暴露端口（如果需要 HTTP API）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/src'); from claude_memory.utils.error_handling import ErrorHandler; print('healthy')" || exit 1

# 启动脚本
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["mcp"]