# AI 观察室 — Docker 部署 (uv + pyproject.toml)
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 先复制依赖文件（利用 Docker 层缓存）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制应用代码
COPY . .

# 安装项目本身
RUN uv sync --frozen --no-dev

# 初始化数据库
RUN uv run python -c "from src.engine.db_core import init_db; init_db()"

# 数据持久化目录
VOLUME /app/data

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
