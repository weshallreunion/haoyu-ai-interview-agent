FROM python:3.12-slim

# 不生成 Python 缓存文件
ENV PYTHONDONTWRITEBYTECODE=1

# 日志立即输出到云端部署日志
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 先复制依赖文件，充分利用 Docker 构建缓存
COPY requirements.txt ./requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# 复制运行所需文件
COPY app ./app
COPY frontend ./frontend
COPY knowledge ./knowledge

# SQLite 数据目录
RUN mkdir -p /app/data

EXPOSE 8000

# 同时兼容本地端口 8000 和 Railway 注入的 PORT
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)" || exit 1

# Railway 有 PORT 时使用 PORT，本地运行时默认使用 8000
CMD ["sh", "-c", "python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]